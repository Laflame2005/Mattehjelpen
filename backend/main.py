"""Koblingslaget for MatteHjelpen. Start: uvicorn backend.main:app --reload.

POST /solve returnerer nøyaktig seks felt, også ved feil. Detaljer fra
valideringen og faktiske verktøykall legges i steg, slik at eksisterende
frontend kan vise dem uten nye responsfelt.

HTTP 400: ugyldig input. 502: modell/API-feil. 500: intern feil.
En ferdig beregning som ikke består kontroll, gir HTTP 200 og validert=False.
Manglende token-/prisdata vises som "ukjent", aldri som oppdiktet null.
Denne appen er beregnet for lokal undervisning, uten autentisering.
"""

import json
import math
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, StrictStr, field_validator

from . import llm_client, validator

app = FastAPI(title='MatteHjelpen')
app.add_middleware(CORSMiddleware, allow_origins=['*'],
                   allow_methods=['GET', 'POST'], allow_headers=['*'])
FRONTEND = Path(__file__).resolve().parents[1] / 'frontend' / 'index.html'


class Oppgave(BaseModel):
    oppgave: StrictStr = Field(min_length=1, max_length=6000)

    @field_validator('oppgave')
    @classmethod
    def ikke_tom(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Oppgaven er tom.')
        return value


def _feil(status, message, previous=None):
    """Samme seks felt ved feil; behold kjent forbruk etter et fullført modellkall."""
    previous = previous or {}
    return JSONResponse(status_code=status, content={
        'svar': message, 'steg': ['Ingen verifisert løsning er tilgjengelig.'],
        'formler_brukt': [], 'validert': False,
        'tokens_brukt': previous.get('tokens_brukt', 'ukjent'),
        'estimert_kostnad': previous.get('estimert_kostnad', 'ukjent'),
    })


@app.exception_handler(RequestValidationError)
async def ugyldig_input(request: Request, exc: RequestValidationError):
    return _feil(400, 'Skriv en oppgave på 1–6000 tegn. Forespørselen må ha JSON-feltet oppgave som tekst.')


@app.get('/')
async def index():
    if not FRONTEND.is_file():
        return _feil(500, 'Frontend-filen mangler. Kontroller at frontend/index.html finnes.')
    return FileResponse(FRONTEND)


def _kontroller_svar(result):
    """Kontroller grensesnittet før vi sender svaret videre til frontend."""
    if not isinstance(result, dict) or not isinstance(result.get('svar'), str):
        raise ValueError('Ugyldig modellrespons.')
    if not isinstance(result.get('steg'), list) or not all(isinstance(s, str) for s in result['steg']):
        raise ValueError('Ugyldige løsningssteg.')
    if not isinstance(result.get('formler_brukt'), list):
        raise ValueError('Ugyldige formelreferanser.')
    for key in ('tokens_brukt', 'estimert_kostnad'):
        value = result.get(key, 'ukjent')
        if value != 'ukjent' and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError('Ugyldig token- eller kostnadstall.')


def _valider(oppgave, result):
    """Valider alle tilknyttede sluttresultater fra faktiske vellykkede kall."""
    grounds = result.get('valideringsgrunnlag', [])
    steps = []
    if not grounds:
        # Behold kontrakten også for enkle svar og skolens simulerte selvtest.
        check = validator.validate(oppgave, result['svar'])
        steps.append('Ikke verifisert: ingen sluttresultater er koblet til faktiske verktøykall. '
                     + check.get('detaljer', 'Ingen kontrollgrunnlag.'))
        return False, steps
    if result.get('use_tools') is not True or result.get('oppgavetype') != 'beregning':
        return False, ['Ikke verifisert: tools er av eller oppgaven er ikke klassifisert som en beregning.']
    by_id = {row['tool_call_id']: row for row in result.get('verktoylogg', [])}
    passed = True
    for basis in grounds:
        record = by_id.get(basis.get('tool_call_id'))
        if (not record or 'feil' in record['output'] or 'resultat' not in record['output']
                or record['navn'] != basis.get('verktoy')
                or record['argumenter'] != basis.get('argumenter')
                or record['output']['resultat'] != basis.get('resultat')):
            passed = False
            steps.append('Kontroll feilet: sluttresultatet samsvarer ikke med et vellykket verktøykall.')
            continue
        problem = json.dumps({'verktoy': basis['verktoy'], 'argumenter': basis['argumenter']}, ensure_ascii=False)
        check = validator.validate(problem, basis['resultat'])
        if not isinstance(check, dict) or type(check.get('validert')) is not bool or not isinstance(check.get('detaljer'), str):
            raise ValueError('Validatoren returnerte feil format.')
        passed = passed and check['validert']
        steps.append(f"Kontroll av {basis['verktoy']}: {check['detaljer']}")
    return passed, steps


@app.post('/solve')
def solve(oppgave: Oppgave):
    # Synkron rute: FastAPI kjører det blokkerende SDK-kallet i en arbeidstråd.
    try:
        result = llm_client.solve_task(oppgave.oppgave)
        _kontroller_svar(result)
    except ValueError:
        return _feil(502, 'Modellen kunne ikke levere et brukbart svar. Kontroller API_KEY, MODEL_NAME og '
                     'API_BASE_URL i .env, tilgjengelig kvote og modellens støtte for tools. '
                     'Feilen kan også skyldes ugyldig svarformat eller for mange modellrunder. Prøv igjen med en enklere oppgave.')
    except Exception:
        return _feil(500, 'En intern feil oppstod under løsing. Ingen løsning er godkjent.')
    try:
        passed, checks = _valider(oppgave.oppgave, result)
        steps = list(result['steg'])
        steps.extend(checks)
        for warning in result.get('advarsler', []):
            steps.append('Merknad fra modellklienten: ' + str(warning))
        for call in result.get('verktoylogg', []):
            steps.append('Faktisk verktøykall: ' + call['navn'] + '\nArgumenter: '
                         + json.dumps(call['argumenter'], ensure_ascii=False)
                         + '\nResultat: ' + json.dumps(call['output'], ensure_ascii=False))
        if passed:
            heading = 'Numeriske stikkprøver bestått for de tilknyttede beregningssvarene. '
        else:
            heading = 'IKKE VERIFISERT SOM KORREKT: kontrollen feilet eller kunne ikke gjennomføres. '
        heading += 'Dette verifiserer ikke hele forklaringen eller at tekstoppgaven er tolket riktig.'
        interpretation = '\nModellens tolkning: ' + result['tolkning'] if result.get('tolkning') else ''
        return {'svar': heading + interpretation + '\n\n' + result['svar'],
                'steg': steps, 'formler_brukt': result['formler_brukt'], 'validert': passed,
                'tokens_brukt': result.get('tokens_brukt', 'ukjent'),
                'estimert_kostnad': result.get('estimert_kostnad', 'ukjent')}
    except Exception:
        return _feil(500, 'Det oppstod en intern feil under kontrollen av svaret. Løsningen er ikke godkjent.', result)
