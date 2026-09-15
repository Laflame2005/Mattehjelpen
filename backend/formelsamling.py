"""Formelsamling for MatteHjelpen – foreløpig utvalg basert på oppgavekravene.

Beholder ID-ene og kapittelhenvisningene fra de seks opprinnelige oppføringene.
LaTeX er renset for formatering som kom inn ved kopiering.

VIKTIG: Gruppen har ennå ikke oppgitt bokutgave eller sidetall. Referansene
fra skjelettet er ikke kontrollert mot en bestemt utgave. Nye oppføringer har
foreløpige bok-/temahenvisninger, ikke bekreftede kapittel- eller sidetall.
Dette markeres i referansefeltet slik at også modellen og frontend ser det.
Før innlevering må gruppen velge 3–5 faktiske pensumformler og kontrollere
referansene mot undervisningsmaterialet. En bestått selvtest sjekker bare
strukturen, ikke at kildene er riktige eller at formelen brukes relevant.
"""

FORMELSAMLING = {
    "D1": {
        "navn": "Produktregelen",
        "formel": r"(uv)' = u'v + uv'",
        "referanse": "Thomas' Calculus, kap. 3 (fra skjelettet; utgave og side må kontrolleres).",
        "bruk": "Når et produkt av to deriverbare funksjoner skal deriveres.",
    },
    "D2": {
        "navn": "Kjerneregelen",
        "formel": r"\frac{dy}{dx}=\frac{dy}{du}\cdot\frac{du}{dx}",
        "referanse": "Thomas' Calculus, kap. 3 (fra skjelettet; utgave og side må kontrolleres).",
        "bruk": "Når en sammensatt funksjon skal deriveres og de aktuelle derivertene finnes.",
    },
    "I1": {
        "navn": "Delvis integrasjon",
        "formel": r"\int u\,dv=uv-\int v\,du",
        "referanse": "Thomas' Calculus, kap. 8 (fra skjelettet; utgave og side må kontrolleres).",
        "bruk": "Når integralet inneholder et produkt som blir enklere etter derivasjon av én faktor; ta med integrasjonskonstanten.",
    },
    "O1": {
        "navn": "Karakteristisk ligning (2. ordens lineær ODE)",
        "formel": r"ay''+by'+cy=0\ \Longrightarrow\ ar^2+br+c=0,\qquad a\ne0",
        "referanse": "Edwards & Penney, kap. 3 (fra skjelettet; utgave og side må kontrolleres).",
        "bruk": "Når en homogen lineær differensialligning av andre orden med konstante koeffisienter skal løses med y=e^{rx}.",
    },
    "K1": {
        "navn": "Eulers formel",
        "formel": r"e^{i\theta}=\cos\theta+i\sin\theta",
        "referanse": "Buanes: Komplekse tall (fra skjelettet; dokumentversjon og side må kontrolleres).",
        "bruk": "Når komplekse tall skal kobles mellom eksponentialform og trigonometrisk form, med reell vinkel i radianer.",
    },
    "M1": {
        "navn": "Determinant (2x2)",
        "formel": r"\det\begin{pmatrix}a&b\\c&d\end{pmatrix}=ad-bc",
        "referanse": "Edwards & Penney, kap. 4 (fra skjelettet; utgave og side må kontrolleres).",
        "bruk": "Når determinanten til en 2x2-matrise skal beregnes eller inverterbarhet vurderes.",
    },
    "D3": {
        "navn": "Kvotientregelen",
        "formel": r"\left(\frac{u}{v}\right)'=\frac{u'v-uv'}{v^2},\qquad v\ne0",
        "referanse": "FORELØPIG: Thomas' Calculus – derivasjonsregler; utgave, kapittel og side må kontrolleres.",
        "bruk": "Når en kvotient av to deriverbare funksjoner skal deriveres og nevneren ikke er null.",
    },
    "D4": {
        "navn": "Potensregelen for derivasjon",
        "formel": r"\frac{d}{dx}x^n=nx^{n-1}",
        "referanse": "FORELØPIG: Thomas' Calculus – derivasjonsregler; utgave, kapittel og side må kontrolleres.",
        "bruk": "Når en potens med konstant eksponent skal deriveres på et område der regelen er definert, for eksempel x>0 for reell eksponent.",
    },
    "I2": {
        "navn": "Potensregelen for integrasjon",
        "formel": r"\int x^n\,dx=\frac{x^{n+1}}{n+1}+C,\qquad n\ne-1",
        "referanse": "FORELØPIG: Thomas' Calculus – antideriverte; utgave, kapittel og side må kontrolleres.",
        "bruk": "Når en potens med konstant eksponent ulik -1 skal integreres på et gyldig definisjonsområde.",
    },
    "I3": {
        "navn": "Substitusjon",
        "formel": r"u=g(x),\quad du=g'(x)\,dx,\qquad\int f(g(x))g'(x)\,dx=\int f(u)\,du",
        "referanse": "FORELØPIG: Thomas' Calculus – substitusjon i integraler; utgave, kapittel og side må kontrolleres.",
        "bruk": "Når et variabelskifte forenkler integralet; sett tilbake den opprinnelige variabelen og ta med C ved ubestemt integrasjon.",
    },
    "I4": {
        "navn": "Logaritmeintegralet",
        "formel": r"\int\frac{1}{x}\,dx=\ln|x|+C,\qquad x\ne0",
        "referanse": "FORELØPIG: Thomas' Calculus – logaritmefunksjonen og integrasjon; utgave, kapittel og side må kontrolleres.",
        "bruk": "Når 1/x integreres over et reelt intervall som ikke inneholder null.",
    },
    "M2": {
        "navn": "Egenverdier",
        "formel": r"A\mathbf{v}=\lambda\mathbf{v},\quad\mathbf{v}\ne\mathbf{0},\qquad\det(A-\lambda I)=0",
        "referanse": "FORELØPIG: Edwards & Penney – egenverdier og egenvektorer; utgave, kapittel og side må kontrolleres.",
        "bruk": "Når egenverdier til en kvadratisk matrise, blant annet 2x2 og 3x3, skal finnes fra den karakteristiske ligningen.",
    },
    "M3": {
        "navn": "Lineært ligningssystem med invertibel matrise",
        "formel": r"A\mathbf{x}=\mathbf{b}\ \Longrightarrow\ \mathbf{x}=A^{-1}\mathbf{b},\qquad\det(A)\ne0",
        "referanse": "FORELØPIG: Edwards & Penney – lineære ligningssystemer og matriser; utgave, kapittel og side må kontrolleres.",
        "bruk": "Når et kvadratisk system har en entydig løsning; i beregninger kan Gauss-eliminasjon eller LU brukes uten å danne inversen.",
    },
    "M4": {
        "navn": "Determinant (3x3)",
        "formel": r"\det\begin{pmatrix}a&b&c\\d&e&f\\g&h&i\end{pmatrix}=a(ei-fh)-b(di-fg)+c(dh-eg)",
        "referanse": "FORELØPIG: Edwards & Penney – determinanter; utgave, kapittel og side må kontrolleres.",
        "bruk": "Når determinanten til en 3x3-matrise beregnes ved kofaktorutvikling langs første rad.",
    },
    "K2": {
        "navn": "De Moivres formel",
        "formel": r"\bigl(r(\cos\theta+i\sin\theta)\bigr)^n=r^n\bigl(\cos(n\theta)+i\sin(n\theta)\bigr)",
        "referanse": "FORELØPIG: Buanes: Komplekse tall – finn og kontroller eventuell omtale av De Moivres formel, med side; velg annen pensumkilde hvis den mangler.",
        "bruk": "Når et komplekst tall på polarform opphøyes i en positiv heltallspotens, med reell vinkel og r som modulus.",
    },
}
