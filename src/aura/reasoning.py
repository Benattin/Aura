from __future__ import annotations

import re

_REASON = re.compile(
    r"\b("
    r"por\s*qu[eê]|porque|como\s+funciona|explique|explica|analise|analis[ae]|"
    r"compare|compar[ae]|diferen[cç]a|melhor\s+op[cç][aã]o|"
    r"qual\s+(?:é|e)\s+(?:o|a)\s+melhor|passo\s+a\s+passo|"
    r"resolv[ae]|calcule|quanto\s+[ée]|vantagens?|desvantagens?|"
    r"pr[oó]s?\s+e\s+contras?|estrat[eé]gia|planej\w*|decid\w*|"
    r"problema|solu[cç][aã]o|justifique|argumente|avalie|avalia|"
    r"entenda|entender|compreenda|racioc[ií]nio|pense|pensando|"
    r"por\s+qu[eê]\s+raz[aã]o|o\s+que\s+(?:voc[eê]|vc)\s+acha|"
    r"me\s+ajud[ae]\s+a\s+(?:entender|decidir|escolher)"
    r")\b",
    re.I,
)
_SKIP = re.compile(
    r"^(oi|ol[aá]|hey|bom\s+dia|boa\s+tarde|boa\s+noite|obrigad|valeu|tchau|"
    r"para|stop|pare|volume|toca|abre|youtube|spotify|gmail)\b",
    re.I,
)
_PROJECT = re.compile(
    r"\b(fa[cç]a|cri[ae]|mont[ae]|desenvolv\w*)\s+.*\b(projeto|site|app|sistema)\b",
    re.I,
)

REASONING_ANALYSIS = (
    "\nMODO ANÁLISE (não responda ao senhor ainda):\n"
    "1. Reformule o pedido em uma frase.\n"
    "2. Liste fatos conhecidos e o que falta saber.\n"
    "3. Monte o raciocínio em passos curtos.\n"
    "4. Antecipe erros comuns e verifique coerência.\n"
    "Responda só com a análise, em tópicos."
)

REASONING_ANSWER = (
    "Com base na sua análise interna, responda ao senhor de forma clara, "
    "correta e completa. Não mencione a análise interna nem diga 'com base na análise'."
)


def needs_reasoning(text: str) -> bool:
    t = text.strip()
    if len(t) < 10:
        return False
    if _SKIP.search(t):
        return False
    if _PROJECT.search(t):
        return True
    if "?" in t:
        return True
    if len(t.split()) >= 14:
        return True
    return bool(_REASON.search(t))
