"""Ærlig numerisk validering for MatteHjelpen.

validate(problem: str, losning: str) -> dict med validert og detaljer.
Støtter ODE i y(x), derivasjon og ubestemte integraler. Andre oppgavetyper
returnerer eksplisitt ikke_verifisert, aldri en oppdiktet godkjenning.

Direkte ODE-eksempel (også brukt av skolens selvtest):
    validate("Eq(y(x).diff(x), y(x))", "y(x) = C1*exp(x)")

For main.py: send maskinlesbart problem som JSON-tekst fra klientens faktiske
valideringsgrunnlag, ikke modellens frie forklaring:
    problem = json.dumps({"verktoy": "integrate",
                          "argumenter": {"uttrykk": "2*x", "variabel": "x"}})
    validate(problem, "x**2")

Toleransen er absolutt 1e-6. Tre tilfeldige, endelige, reelle punkter kreves.
Ved ODE settes kandidatfunksjonen og dens deriverte inn i original ligning.
Ved integrasjon deriveres kandidaten og sammenlignes med integranden.
Ved derivasjon brukes en numerisk sentraldifferanse i to steglengder.
Konstanter C, C1 osv. trekkes også tilfeldig. Andre parametere støttes ikke.

Stikkprøver er ikke bevis: tolkning, globalt definisjonsområde, fullstendighet,
start-/randbetingelser og hele forklaringsteksten er ikke verifisert.
Tidsgrense for beregning må håndteres av den som kaller validatoren.
"""

import ast
import json
import math
import random
import re

import sympy as sp
from .tools import parse, symbol

TOLERANSE = 1e-6
ANTALL_PUNKTER = 3
MAKS_FORSOK = 40


def _svar(status, text, points=None):
    """Bare beståtte numeriske kontroller gir validert=True."""
    return {'validert': status == 'bestatt', 'status': status,
            'detaljer': text, 'punkter': points or []}


def _ligning(text):
    """Les a=b, uttrykk=0 eller Eq(a,b) uten eval eller fri Python-kjøring."""
    if not isinstance(text, str) or len(text) > 1000:
        raise ValueError('Ligningen må være en kort tekststreng.')
    text = text.strip()
    if text.startswith('Eq('):
        node = ast.parse(text, mode='eval').body
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'Eq' and len(node.args) == 2 and not node.keywords):
            raise ValueError('Bruk Eq(venstreside, høyreside).')
        return parse(ast.unparse(node.args[0])), parse(ast.unparse(node.args[1]))
    parts = text.split('=')
    if len(parts) == 1:
        parts.append('0')
    if len(parts) != 2:
        raise ValueError('Ligningen må ha høyst ett likhetstegn.')
    return parse(parts[0]), parse(parts[1])


def _real(value):
    """Evaluer med høy presisjon og avvis komplekse eller uendelige verdier."""
    number = complex(value.evalf(40))
    if not (math.isfinite(number.real) and math.isfinite(number.imag)):
        raise ValueError('Ikke endelig tall.')
    if abs(number.imag) > 1e-12:
        raise ValueError('Ikke reelt evalueringspunkt.')
    return number.real


def _forbered(problem, losning):
    """Bygg kontrollstørrelser fra oppgaven og den oppgitte kandidaten."""
    if problem.lstrip().startswith('{'):
        spec = json.loads(problem)
        if not isinstance(spec, dict) or not isinstance(spec.get('argumenter'), dict):
            raise ValueError('Maskinlesbart problem mangler argumenter.')
        kind, args = spec.get('verktoy'), spec['argumenter']
    else:
        kind, args = 'solve_ode', {'ligning': problem}
    if kind not in ('solve_ode', 'derive', 'integrate'):
        return None
    if kind == 'solve_ode':
        x = sp.Symbol('x')
        y = sp.Function('y')(x)
        lhs, rhs = _ligning(args['ligning'])
        if not (lhs.has(sp.Derivative) or rhs.has(sp.Derivative)):
            return None
        solution_lhs, candidate = _ligning(losning)
        if solution_lhs != y or candidate.has(y, sp.Derivative):
            raise ValueError('ODE-kandidaten må være eksplisitt: y(x) = et uttrykk uten y(x).')
        checks = [lhs.subs(y, candidate).doit(), rhs.subs(y, candidate).doit()]
        domain = [candidate]
        title = 'ODE: satte kandidatfunksjonen og dens deriverte inn i ligningens to sider'
    else:
        x = symbol(args.get('variabel', 'x'))
        original = parse(args['uttrykk'])
        candidate = parse(losning)
        # Reell x lar SymPy blant annet derivere log(Abs(x)) på gyldige punkter.
        real_x = sp.Symbol(str(x), real=True)
        original, candidate = original.xreplace({x: real_x}), candidate.xreplace({x: real_x})
        x = real_x
        domain = [original, candidate]
        if kind == 'integrate':
            checks = [sp.diff(candidate, x), original]
            title = 'Integral: deriverte antideriverten og sammenlignet med integranden'
        else:
            h = sp.Rational(1, 100000)
            approx = (original.subs(x, x+h) - original.subs(x, x-h))/(2*h)
            approx_small = (original.subs(x, x+h/2) - original.subs(x, x-h/2))/h
            checks = [candidate, approx, approx_small]
            domain += [original.subs(x,x+h), original.subs(x,x-h),
                       original.subs(x,x+h/2), original.subs(x,x-h/2)]
            title = 'Derivasjon: sammenlignet kandidaten med sentraldifferanse med h=1e-5 og h=5e-6'
    expressions = checks + domain
    if any(e.has(sp.Derivative, sp.Integral) or e.atoms(sp.core.function.AppliedUndef)
           for e in expressions):
        raise ValueError('Kontrolluttrykket inneholder funksjoner eller operasjoner som ikke kunne evalueres.')
    variables = set().union(*(e.free_symbols for e in expressions))
    constants = variables - {x}
    if any(not re.fullmatch(r'C\d*', str(c)) for c in constants):
        raise ValueError('Andre ukjente parametere enn integrasjonskonstanter C, C1 osv. må få verdier først.')
    return kind, x, sorted(constants, key=str), checks, domain, title


def validate(problem: str, losning: str) -> dict:
    """Kontroller tre punkter; returner ærlig feil eller ikke-verifisert ved begrensninger."""
    if not isinstance(problem, str) or not isinstance(losning, str):
        return _svar('ikke_verifisert', 'Validering krever problem og løsning som tekst.')
    if not problem.strip() or not losning.strip() or len(problem) > 4000 or len(losning) > 1000:
        return _svar('ikke_verifisert', 'Problem eller løsning er tom eller for lang til denne validatoren.')
    try:
        prepared = _forbered(problem, losning)
    except (ValueError, TypeError, SyntaxError, KeyError, NotImplementedError, RecursionError):
        return _svar('ikke_verifisert',
            'Kunne ikke tolke eller klargjøre denne oppgaven for numerisk kontroll. '
            'Bruk en ODE som Eq(y(x).diff(x), y(x)) og løsning y(x)=C1*exp(x), '
            'eller maskinlesbare argumenter for derive/integrate. Ingen godkjenning er gitt.')
    if prepared is None:
        return _svar('ikke_verifisert',
            'Denne validatoren støtter ODE, derivasjon og ubestemte integraler. '
            'Bevis, begrepsforklaringer, algebraiske ligninger, matriser og komplekse '
            'operasjoner er ikke kontrollert av denne versjonen.')
    kind, x, constants, checks, domain, title = prepared
    rng = random.SystemRandom()
    # Unike tilfeldige x-verdier fra -5 til 5; null unngås som vanlig singularitet.
    candidates = rng.sample([sp.Rational(n, 10) for n in range(-50,51) if n], MAKS_FORSOK)
    points, skipped = [], 0
    for point in candidates:
        substitutions = {x: point}
        substitutions.update({c: sp.Rational(rng.choice([-7,-3,-1,1,3,7]), 2) for c in constants})
        try:
            for expr in domain:
                _real(expr.subs(substitutions))
            values = [_real(expr.subs(substitutions)) for expr in checks]
            if kind == 'derive' and abs(values[1]-values[2]) > TOLERANSE:
                # An unstable finite difference is not evidence the candidate is wrong.
                skipped += 1
                continue
            error = max(abs(values[0]-value) for value in values[1:])
        except (ValueError, TypeError, OverflowError, ZeroDivisionError):
            skipped += 1
            continue
        row = {'innsetting': {str(k): float(v) for k,v in substitutions.items()},
               'kontrollverdier': values, 'avvik': error, 'bestatt': error <= TOLERANSE}
        points.append(row)
        if len(points) == ANTALL_PUNKTER:
            break
    details = '; '.join(f"{p['innsetting']}: avvik={p['avvik']:.3g}" for p in points)
    prefix = f'{title}. Absolutt toleranse {TOLERANSE:g}. Punkter: {details or "ingen gyldige"}. '
    if any(not p['bestatt'] for p in points):
        return _svar('feilet', prefix + 'Minst én numerisk kontroll feilet. Løsningen godkjennes ikke.', points)
    if len(points) < ANTALL_PUNKTER:
        return _svar('ikke_verifisert', prefix +
            f'Fant bare {len(points)} gyldige punkter; krever tre. {skipped} punkter kunne ikke brukes. '
            'Definisjonsområde eller numerisk stabilitet krever manuell kontroll.', points)
    return _svar('bestatt', prefix +
        'Tre numeriske kontroller bestått. Dette er stikkprøver for den oppgitte '
        'matematiske tolkningen, ikke et bevis eller en kontroll av hele definisjonsområdet, '
        'fullstendig løsningsmengde eller eventuelle start-/randbetingelser.', points)
