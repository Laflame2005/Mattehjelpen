"""LLM-klient: modellen forklarer, tools.py beregner.

Installer avhengighetene fra requirements.txt (openai og python-dotenv).
API_KEY, MODEL_NAME og API_BASE_URL leses fra prosjektets .env.
Valgfrie INPUT_NOK_PER_MILLION og OUTPUT_NOK_PER_MILLION gir prisestimat.
Uten priser eller komplett tokenrapport blir kostnaden "ukjent".
Prisene må tilhøre valgt modell; sett 0 bare når gratispris er bekreftet.

USE_TOOLS er eksperimentbryteren. Start serveren på nytt etter endringer.
Denne modulen setter IKKE validert. Det gjøres senere av validator/main.
valideringsgrunnlag inneholder bare resultater koblet til faktiske kall;
fritekst, oppgavetolkning og formelbruk må fortsatt vurderes selvstendig.
"""

import inspect
import json
import math
import multiprocessing as mp
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError

from . import tools
from .formelsamling import FORMELSAMLING

USE_TOOLS = True  # Aha-bryter: False utelater alle tools fra API-forespørselen.
MAX_ROUNDS = 8
MAX_TOOL_CALLS = 20
TOOL_TIMEOUT = 12  # sekunder per SymPy-beregning

SYSTEMPROMPT = """Du er en matematikklærer for ingeniørstudenter. Bruk verktøyene
(SymPy) til all beregning når oppgaven lar seg beregne slik – du skal ALDRI late
som du har brukt et verktøy du ikke faktisk kalte. Kan oppgaven ikke beregnes
(f.eks. et bevis eller en begrepsforklaring), resonnerer du i tekst og sier
 eksplisitt at svaret IKKE er verifisert av et verktøy.
Forklar hvert steg pedagogisk på norsk, og oppgi nøyaktig hvilke formler/verktøy
du faktisk brukte. Knytt hver formel-ID til steget der den brukes, og ta med navn
og referanse fra formelsamlingen. Hvis du er usikker, si det eksplisitt.

Tillegg: Bruk enkelt norsk. Forklar symbolene og hvorfor hvert steg gjøres.
Ved tvetydigheter, som sin^-1(x), spør om avklaring fremfor å gjette.
Behold forbehold som FORELØPIG og 'må kontrolleres' i referansene.
En gyldig formel-ID er ikke bevis på riktig formelbruk.
Et vellykket verktøykall er ikke en numerisk validering eller et bevis.
Ikke påstå at numerisk validering er utført; validatoren gjør dette senere.
Hvis et verktøy gir feil, forklar feilen eller rett argumentene. Ikke dikt et resultat.

Returner til slutt KUN et gyldig JSON-objekt med disse feltene:
- svar: norsk forklaring og svar som tekst.
- steg: liste med forklarte steg som strenger.
- formler_brukt: liste av objekter med id og steg (stegnummer fra 1).
- tolkning: din presise tolkning av oppgaven som tekst.
- oppgavetype: beregning, bevis, begrep eller avklaring.
- sluttresultater: liste av objekter med tool_call_id og resultat.
Kopier resultat-strengen eksakt fra det faktiske verktøykallet som gir et
sluttresultat. Ved flere deloppgaver: ta med alle sluttresultater.
Ved bevis, begrep, avklaring eller tools av: bruk tom liste for sluttresultater.
Ikke legg JSON i markdown-gjerder. Escape LaTeX-backslash korrekt i JSON.
"""

# Eksplisitt register: modellen kan aldri be om vilkårlige Python-funksjoner.
REGISTRY = {name: getattr(tools, name) for name in (
    'derive', 'integrate', 'solve_equation', 'solve_ode', 'matrix_op', 'complex_op'
)}


def _tool_worker(sender, name, arguments):
    """Kjør ett tillatt verktøy i egen prosess som kan stoppes ved tidsavbrudd."""
    try:
        result = REGISTRY[name](**arguments)
        if not isinstance(result, dict):
            result = {'feil': 'Verktøyet returnerte ikke en dict.'}
        sender.send(result)
    except Exception:
        sender.send({'feil': 'Verktøyet feilet. Kontroller operasjon og argumenter.'})
    finally:
        sender.close()


def _run_tool(name, arguments):
    """Valider argumentnavn og begrens kjøretiden for ett faktisk kall."""
    if name not in REGISTRY:
        return {'feil': 'Ukjent verktøy: bare de seks definerte verktøyene er tillatt.'}
    if not isinstance(arguments, dict):
        return {'feil': 'Verktøyargumentene må være et JSON-objekt.'}
    try:
        inspect.signature(REGISTRY[name]).bind(**arguments)
    except TypeError:
        return {'feil': 'Argumentene stemmer ikke med verktøyets parametere.'}
    context = mp.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_tool_worker, args=(sender, name, arguments), daemon=True)
    process.start()
    sender.close()
    try:
        if receiver.poll(TOOL_TIMEOUT):
            try:
                return receiver.recv()
            except EOFError:
                return {'feil': 'Beregningen stoppet uten resultat.'}
        return {'feil': 'Beregningen overskred tidsgrensen på 12 sekunder.'}
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        receiver.close()


def _final_response(content, log, use_tools):
    """Kontroller modellformat, formel-ID-er og kobling til beregningsresultater."""
    try:
        data = json.loads(content)
    except (ValueError, TypeError):
        raise ValueError('Modellen returnerte ikke gyldig JSON. Prøv på nytt eller bytt modell.') from None
    if not isinstance(data, dict):
        raise ValueError('Modellsvaret må være et JSON-objekt.')
    if not isinstance(data.get('svar'), str) or not data['svar'].strip():
        raise ValueError('Modellsvaret mangler svartekst.')
    steps = data.get('steg')
    if not isinstance(steps, list) or not steps or not all(isinstance(v, str) and v.strip() for v in steps):
        raise ValueError('Modellsvaret mangler en liste med forklarte steg.')
    formulas = data.get('formler_brukt', [])
    if not isinstance(formulas, list):
        raise ValueError('formler_brukt må være en liste.')
    checked = []
    for item in formulas:
        if not isinstance(item, dict):
            raise ValueError('En formeloppføring har feil format.')
        fid, step = item.get('id'), item.get('steg')
        if not isinstance(fid, str) or fid not in FORMELSAMLING:
            raise ValueError('Modellen oppga en ukjent formel-ID. Svaret avvises; prøv på nytt.')
        if type(step) is not int or not 1 <= step <= len(steps):
            raise ValueError('Modellen koblet en formel til et steg som ikke finnes.')
        checked.append({'id': fid, 'steg': step, **FORMELSAMLING[fid]})
    kind = data.get('oppgavetype')
    if kind not in ('beregning', 'bevis', 'begrep', 'avklaring'):
        raise ValueError('Modellen må oppgi gyldig oppgavetype.')
    interpretation = data.get('tolkning')
    if not isinstance(interpretation, str) or not interpretation.strip():
        raise ValueError('Modellen må forklare hvordan oppgaven er tolket.')
    finals = data.get('sluttresultater', [])
    if not isinstance(finals, list):
        raise ValueError('sluttresultater må være en liste.')
    lookup = {row['tool_call_id']: row for row in log}
    grounds, warnings = [], []
    if use_tools and kind == 'beregning':
        for item in finals:
            if not isinstance(item, dict) or not isinstance(item.get('tool_call_id'), str):
                raise ValueError('Ugyldig kobling mellom sluttresultat og verktøykall.')
            row = lookup.get(item['tool_call_id'])
            if row is None or 'resultat' not in row['output'] or 'feil' in row['output']:
                raise ValueError('Sluttresultatet peker ikke til et vellykket verktøykall.')
            if item.get('resultat') != row['output']['resultat']:
                raise ValueError('Oppgitt sluttresultat avviker fra det faktiske verktøyresultatet.')
            grounds.append({'tool_call_id': row['tool_call_id'], 'verktoy': row['navn'],
                            'argumenter': row['argumenter'], 'resultat': row['output']['resultat']})
        if not grounds:
            warnings.append('Ingen sluttresultater er koblet til vellykkede beregningskall.')
    else:
        finals = []
    if not grounds:
        warning = 'Svaret er IKKE verifisert av et verktøy.'
        data['svar'] = warning + '\n\n' + data['svar']
        warnings.append(warning)
    else:
        warnings.append('Verktøyresultater finnes. Numerisk validering må utføres separat; tolkning og forklaring er ikke automatisk kontrollert.')
    return {'svar': data['svar'], 'steg': steps, 'formler_brukt': checked,
            'tolkning': interpretation, 'oppgavetype': kind, 'use_tools': use_tools,
            'verktoylogg': log, 'sluttresultater': finals,
            'valideringsgrunnlag': grounds, 'advarsler': warnings}


def _rate(name):
    """Les en valgfri NOK-pris, uten å anta at manglende pris betyr gratis."""
    value = os.getenv(name, '').strip()
    if not value:
        return None
    try:
        number = float(value)
    except ValueError:
        raise ValueError(f'{name} må være et tall, med punktum som desimaltegn.') from None
    if not math.isfinite(number) or number < 0:
        raise ValueError(f'{name} må være et endelig tall større enn eller lik null.')
    return number


def solve_task(oppgave: str) -> dict:
    """Løs oppgaven via API og ekte tools. Returner JSON-kompatibel dict uten validert."""
    if not isinstance(oppgave, str) or not oppgave.strip() or len(oppgave) > 6000:
        raise ValueError('Oppgaven må være tekst på mellom 1 og 6000 tegn.')
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    key, model, base = (os.getenv(name, '').strip() for name in ('API_KEY', 'MODEL_NAME', 'API_BASE_URL'))
    if not all((key, model, base)):
        raise ValueError('Fyll inn API_KEY, MODEL_NAME og API_BASE_URL i .env, og start serveren på nytt.')
    input_rate, output_rate = _rate('INPUT_NOK_PER_MILLION'), _rate('OUTPUT_NOK_PER_MILLION')
    use_tools = USE_TOOLS
    prompt = SYSTEMPROMPT
    if not use_tools:
        prompt += '\nEKSPERIMENT: Tools er AV. I denne forsøksmodusen kan du beregne selv. Si tydelig at svaret IKKE er verifisert av et verktøy. sluttresultater skal være tom.'
    prompt += '\nFORMELSAMLING:\n' + json.dumps(FORMELSAMLING, ensure_ascii=False, separators=(',', ':'))
    messages = [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': oppgave.strip()}]
    log, input_tokens, output_tokens, usage_complete = [], 0, 0, True
    started = time.monotonic()
    try:
        # Ingen automatiske API-retries: hver modellrunde regnes og logges eksplisitt.
        with OpenAI(api_key=key, base_url=base, timeout=45.0, max_retries=0) as client:
            for round_number in range(1, MAX_ROUNDS + 1):
                request = {'model': model, 'messages': messages, 'max_tokens': 3000}
                if use_tools:
                    request.update(tools=tools.TOOL_DEFINITIONS, tool_choice='auto')
                response = client.chat.completions.create(**request)
                usage = response.usage
                if usage and all(type(v) is int and v >= 0 for v in (usage.prompt_tokens, usage.completion_tokens)):
                    input_tokens += usage.prompt_tokens
                    output_tokens += usage.completion_tokens
                else:
                    usage_complete = False
                if not response.choices:
                    raise ValueError('API-et returnerte ingen svaralternativer.')
                choice = response.choices[0]
                if choice.finish_reason in ('length', 'content_filter'):
                    raise ValueError('Modellsvaret ble avkortet eller stoppet av leverandøren.')
                message = choice.message
                if message.tool_calls:
                    if not use_tools:
                        raise ValueError('Modellen ba om tools selv om tools er avslått.')
                    if round_number == MAX_ROUNDS:
                        raise ValueError('Modellen fullførte ikke innen 8 modellrunder. Prøv en enklere oppgave.')
                    if len(log) + len(message.tool_calls) > MAX_TOOL_CALLS:
                        raise ValueError('Modellen ba om for mange verktøykall (maks 20).')
                    messages.append({'role': 'assistant', 'content': message.content,
                                     'tool_calls': [call.model_dump(exclude_none=True) for call in message.tool_calls]})
                    for call in message.tool_calls:
                        if call.type != 'function':
                            raise ValueError('API-et ba om en verktøytype appen ikke støtter.')
                        if any(row['tool_call_id'] == call.id for row in log):
                            raise ValueError('API-et gjenbrukte en verktøykall-ID; koblingen er tvetydig.')
                        try:
                            arguments = json.loads(call.function.arguments)
                        except (ValueError, TypeError):
                            arguments = None
                            result = {'feil': 'Ugyldig JSON i verktøyargumentene.'}
                        else:
                            result = _run_tool(call.function.name, arguments)
                        log.append({'tool_call_id': call.id, 'navn': call.function.name,
                                    'argumenter': arguments, 'output': result})
                        messages.append({'role': 'tool', 'tool_call_id': call.id,
                                         'content': json.dumps(result, ensure_ascii=False)})
                    continue
                result = _final_response(message.content, log, use_tools)
                cost = 'ukjent'
                if usage_complete and input_rate is not None and output_rate is not None:
                    cost = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
                return {**result, 'oppgave': oppgave.strip(), 'modell': model,
                        'tokens_brukt': input_tokens + output_tokens if usage_complete else 'ukjent',
                        'token_detaljer': {'input': input_tokens, 'output': output_tokens, 'komplett': usage_complete},
                        'estimert_kostnad': cost, 'valuta': 'NOK', 'modellrunder': round_number,
                        'latens_sekunder': round(time.monotonic() - started, 3)}
    except APITimeoutError:
        raise ValueError('Modell-API-et svarte ikke innen tidsgrensen. Prøv igjen.') from None
    except APIConnectionError:
        raise ValueError('Kunne ikke kontakte modell-API-et. Kontroller nettverk og API_BASE_URL.') from None
    except APIStatusError as exc:
        raise ValueError(f'Modell-API-et returnerte HTTP {exc.status_code}. Kontroller nøkkel, modellnavn, kvote og støtte for tools.') from None
    raise ValueError('Modellen fullførte ikke innen grensen for modellrunder.')
