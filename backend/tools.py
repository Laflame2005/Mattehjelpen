"""Deterministiske SymPy-verktøy for MatteHjelpen.

Suksess: {"resultat": str, "latex": str}. Feil: {"feil": norsk forklaring}.
Bruk eksplisitt multiplikasjon: 2*x. ^ og ** betyr potens.
sin^-1(x) avvises: skriv asin(x) eller 1/sin(x).
ODE skrives med y(x), f.eks. Derivative(y(x),x)=y(x) eller y(x).diff(x)=y(x).
Komplekse tall kan bruke både I og j: 1+I eller 1+1j.
Ax=b: bruk en utvidet matrise [A|b] (siste kolonne er b).
Komplekse potenser/røtter: operasjon="potens:3" eller "rotter:3".
Ved operasjon="euler" er tall vinkelen, f.eks. "pi/2".

Dette er beregningsverktøy, ikke validering av modellens tolkning eller bevis.
Parseren tillater bare et begrenset sett matematiske konstruksjoner.
Den er ikke en full ressurs-sandkasse: bruk lokalt, og legg tidsgrenser rundt
verktøykall ved videre utvikling før eventuell offentlig drift.
"""
import ast
import math
from functools import wraps
import re
import sympy as s

FUNCTIONS = {name: getattr(s, name) for name in
             ('sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'sinh', 'cosh',
              'exp', 'log', 'sqrt', 'Abs', 're', 'im', 'conjugate', 'Derivative')}
FUNCTIONS['y'] = s.Function('y')
CONSTANTS = {'pi': s.pi, 'E': s.E, 'I': s.I}


def parse(text):
    text = str(text).strip()
    if re.search(r'(sin|cos|tan)\s*(?:\^|\*\*)\s*\(?\s*-1', text):
        raise ValueError('Tvetydig notasjon: skriv asin(x) for invers sinus eller 1/sin(x) for omvendt verdi.')
    if len(text) > 500:
        raise ValueError('Uttrykket er for langt (maks 500 tegn).')
    tree = ast.parse(text.replace('^', '**'), mode='eval')
    if sum(1 for _ in ast.walk(tree)) > 150:
        raise ValueError('Uttrykket er for komplisert.')

    def visit(n):
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            if not math.isfinite(n.value) or abs(n.value) > 10**12:
                raise ValueError('Tallet er utenfor tillatt område.')
            return s.Rational(str(n.value))
        if isinstance(n, ast.Constant) and type(n.value) is complex:
            z = n.value
            if not all(math.isfinite(v) and abs(v) <= 10**12 for v in (z.real, z.imag)):
                raise ValueError('Det komplekse tallet er utenfor tillatt område.')
            return s.Rational(str(z.real)) + s.I*s.Rational(str(z.imag))
        if isinstance(n, ast.Name) and re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,15}', n.id):
            return CONSTANTS.get(n.id, s.Symbol(n.id))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.UAdd, ast.USub)):
            return visit(n.operand) * (-1 if isinstance(n.op, ast.USub) else 1)
        if isinstance(n, ast.BinOp):
            a, b = visit(n.left), visit(n.right)
            if isinstance(n.op, ast.Add): return a + b
            if isinstance(n.op, ast.Sub): return a - b
            if isinstance(n.op, ast.Mult): return a * b
            if isinstance(n.op, ast.Div): return a / b
            if isinstance(n.op, ast.Pow):
                if b.is_number and (b.is_real is not True or abs(b) > 100):
                    raise ValueError('Eksponent må være reell og mellom -100 og 100.')
                return a ** b
        # Tillat bare .diff(...), aldri vilkårlig attributt-/metodetilgang.
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'diff' and not n.keywords):
            if not 1 <= len(n.args) <= 2:
                raise ValueError('Bruk .diff(x) eller .diff(x, 2).')
            expression = visit(n.func.value)
            variable = visit(n.args[0])
            order = visit(n.args[1]) if len(n.args) == 2 else s.Integer(1)
            if not isinstance(variable, s.Symbol) or not isinstance(order, s.Integer) or not 1 <= order <= 10:
                raise ValueError('Den deriverte krever en variabel og heltallig orden fra 1 til 10.')
            return s.Derivative(expression, variable, order)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCTIONS and not n.keywords:
            return FUNCTIONS[n.func.id](*(visit(a) for a in n.args))
        raise ValueError('Ugyldig matematisk syntaks. Bruk f.eks. x**2, sin(x), I og Derivative(y(x),x).')
    result = visit(tree.body)
    if result.has(s.zoo, s.oo, -s.oo, s.nan):
        raise ValueError('Uttrykket er udefinert eller uendelig, for eksempel ved deling på null.')
    return result


def symbol(name):
    value = parse(name)
    if not isinstance(value, s.Symbol):
        raise ValueError('Variabelen må være ett symbol, for eksempel x.')
    return value


def equation(text):
    parts = text.split('=')
    if len(parts) == 1:
        parts.append('0')
    if len(parts) != 2:
        raise ValueError('Ligningen må ha ett likhetstegn.')
    return s.Eq(parse(parts[0]), parse(parts[1]), evaluate=False)


def matrix(data):
    if not isinstance(data, list) or not 1 <= len(data) <= 6:
        raise ValueError('Matrisen må ha 1–6 rader.')
    if any(not isinstance(row, list) or not 1 <= len(row) <= 7 for row in data):
        raise ValueError('Matrisen må ha 1–7 kolonner (sju bare for [A|b]).')
    if len({len(row) for row in data}) != 1:
        raise ValueError('Alle rader må ha like mange kolonner.')
    return s.Matrix([[parse(v) for v in row] for row in data])


def _trygg(function):
    """Gjør feil om til en konsekvent dict uten å skjule dem som resultater."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (SyntaxError, TypeError):
            return {'feil': 'Ugyldig syntaks eller datatype. Bruk f.eks. x**2 og sin(x).'}
        except Exception as exc:
            return {'feil': 'Beregningen kunne ikke utføres: ' + str(exc)[:300]}
    return wrapped


def _resultat(value):
    """Pakk et SymPy-resultat som tekst og LaTeX."""
    values = list(value.keys()) if isinstance(value, dict) else (value if isinstance(value, (list, tuple)) else [value])
    for item in values:
        if isinstance(item, s.Basic) and item.has(s.zoo, s.oo, -s.oo, s.nan):
            raise ValueError('Resultatet er udefinert eller uendelig.')
        if isinstance(item, s.Basic) and item.has(s.Integral, s.Derivative):
            raise ValueError('SymPy klarte ikke å fullføre beregningen symbolsk.')
    return {'resultat': str(value), 'latex': s.latex(value)}


@_trygg
def derive(uttrykk: str, variabel: str = 'x') -> dict:
    """Deriver uttrykket med hensyn på variabelen, f.eks. x**2 gir 2*x."""
    return _resultat(s.diff(parse(uttrykk), symbol(variabel)))


@_trygg
def integrate(uttrykk: str, variabel: str = 'x') -> dict:
    """Finn én antiderivert. Svaret i forklaringen må inkludere konstanten +C."""
    return _resultat(s.integrate(parse(uttrykk), symbol(variabel)))


@_trygg
def solve_equation(ligning: str, variabel: str = 'x') -> dict:
    """Løs ligning med =. Uten = tolkes uttrykket som lik null; komplekse røtter tillates."""
    eq, x = equation(ligning), symbol(variabel)
    residual = eq.lhs - eq.rhs
    if s.simplify(residual) == 0:
        raise ValueError('Ligningen er en identitet. Alle verdier i originaluttrykkets definisjonsområde kan passe; avklar domenet.')
    roots = s.solve(eq, x)
    if not roots:
        raise ValueError('SymPy fant ingen eksplisitte løsninger. Dette beviser ikke at ingen løsninger finnes.')
    return _resultat(roots)


@_trygg
def solve_ode(ligning: str) -> dict:
    """Løs ODE i y(x), f.eks. Derivative(y(x),x,2)+y(x)=0. Ingen startbetingelser."""
    eq = equation(ligning)
    if not eq.has(s.Derivative):
        raise ValueError('Ingen derivert funnet. Bruk Derivative(y(x),x), eller Derivative(y(x),x,2).')
    return _resultat(s.dsolve(eq, s.Function('y')(s.Symbol('x'))))


@_trygg
def matrix_op(operasjon: str, matrise: list) -> dict:
    """Determinant, invers, egenverdier eller solve med utvidet matrise [A|b]."""
    A = matrix(matrise)
    op = operasjon.strip().lower()
    if op in ('solve', 'los', 'løs', 'ax=b'):
        if A.cols != A.rows + 1:
            raise ValueError('For Ax=b: oppgi n rader og n+1 kolonner. Siste kolonne er b.')
        coefficients, b = A[:, :-1], A[:, -1]
        if coefficients.det() == 0:
            raise ValueError('A er singulær: systemet har ingen entydig løsning. Denne funksjonen støtter bare entydige løsninger.')
        return _resultat(coefficients.LUsolve(b))
    if A.rows != A.cols:
        raise ValueError('Denne operasjonen krever en kvadratisk matrise.')
    if op in ('determinant', 'det'):
        return _resultat(A.det())
    if op in ('invers', 'inverse', 'inv'):
        if A.det() == 0:
            raise ValueError('Matrisen har determinant 0 og ingen invers.')
        return _resultat(A.inv())
    if op in ('egenverdier', 'eigenvalues'):
        return _resultat(A.eigenvals())
    raise ValueError('Ukjent operasjon. Bruk determinant, invers, egenverdier eller solve.')


@_trygg
def complex_op(operasjon: str, tall: str) -> dict:
    """Polarform, potens:n, rotter:n eller Euler fra vinkel. Bruk I som imaginær enhet."""
    op = operasjon.strip().lower()
    z = parse(tall)
    if z.free_symbols or z.is_number is not True:
        raise ValueError('Oppgi et konkret tall, for eksempel 1+I eller pi/2.')
    if op in ('polarform', 'polar'):
        if z == 0:
            return {'resultat': 'Modulus 0; argumentet er udefinert.', 'latex': r'|z|=0,\quad \arg(0)\text{ er udefinert}'}
        r, theta = s.simplify(s.Abs(z)), s.simplify(s.arg(z))
        return {'resultat': f'r={r}, theta={theta}; z=r*exp(I*theta)',
                'latex': rf'r={s.latex(r)},\quad\theta={s.latex(theta)},\quad z=r e^{{i\theta}}'}
    if op in ('euler', 'eulers formel'):
        if z.is_real is not True:
            raise ValueError('Euler-operasjonen forventer en reell vinkel i radianer.')
        return _resultat(s.simplify(s.cos(z) + s.I*s.sin(z)))
    parts = op.split(':')
    if len(parts) != 2 or parts[0] not in ('potens', 'potenser', 'power', 'rotter', 'røtter', 'roots'):
        raise ValueError('Bruk polarform, euler, potens:3 eller rotter:3. Tallet etter : må oppgis.')
    n = int(parts[1])
    if not 1 <= n <= 20:
        raise ValueError('Eksponenten eller rotgraden må være et heltall fra 1 til 20.')
    if parts[0] in ('potens', 'potenser', 'power'):
        return _resultat(s.expand(z**n))
    if z == 0:
        return _resultat([s.Integer(0)])
    roots = [s.simplify(s.Abs(z)**s.Rational(1,n) *
                        s.exp(s.I*(s.arg(z)+2*s.pi*k)/n)) for k in range(n)]
    return _resultat(roots)


def _definition(name, description, properties, required):
    """Lag JSON-schema som samsvarer med Python-funksjonens parametere."""
    return {'type': 'function', 'function': {
        'name': name, 'description': description,
        'parameters': {'type': 'object', 'properties': properties,
                       'required': required, 'additionalProperties': False}}}


_STRING = {'type': 'string'}
_VARIABLE = {'type': 'string', 'description': 'Variabelnavn, standard x.', 'default': 'x'}
TOOL_DEFINITIONS = [
    _definition('derive', 'Deriver. Bruk eksplisitt multiplikasjon og x**2; asin(x) for invers sinus.',
                {'uttrykk': _STRING, 'variabel': _VARIABLE}, ['uttrykk']),
    _definition('integrate', 'Ubestemt integral: returnerer en antiderivert. Forklaringen skal legge til +C.',
                {'uttrykk': _STRING, 'variabel': _VARIABLE}, ['uttrykk']),
    _definition('solve_equation', 'Løs f.eks. x**2=4. Uten = tolkes uttrykket som lik null. Kontroller domenet separat.',
                {'ligning': _STRING, 'variabel': _VARIABLE}, ['ligning']),
    _definition('solve_ode', 'ODE i y(x). Bruk Derivative(y(x),x) eller Derivative(y(x),x,2). Ingen startbetingelser.',
                {'ligning': _STRING}, ['ligning']),
    _definition('matrix_op', 'determinant, invers, egenverdier, solve. For solve bruk utvidet matrise [A|b], f.eks. [[2,0,4],[0,3,9]]. Maks 6 rader.',
                {'operasjon': {'type': 'string', 'enum': ['determinant', 'invers', 'egenverdier', 'solve']},
                 'matrise': {'type': 'array', 'items': {'type': 'array', 'items': {
                     'anyOf': [{'type': 'number'}, {'type': 'string'}]}}}}, ['operasjon', 'matrise']),
    _definition('complex_op', 'Bruk I. Operasjon: polarform, potens:n, rotter:n (n=1–20), euler. For euler er tall en reell vinkel i radianer. Eksempel potens:3 og tall=1+I.',
                {'operasjon': _STRING, 'tall': _STRING}, ['operasjon', 'tall']),
]