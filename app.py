import re
import pandas as pd

def parse_robust(raw: str) -> pd.DataFrame:
    """
    Reconnaît toutes les variantes de :
      • Référence    : ≈ ref, réf, reference
      • Nb de colis  : nbr colis, nombre colis, colis
      • pcs par colis: pcs, pièces, pieces, nombre de pièces
    Et assemble les triplets dans un tableau.
    """
    # On récupère successivement toutes les valeurs trouvées dans l'ordre d'apparition
    refs   = re.findall(r"(?i)(?:ref(?:[ée]rence)?|réf)\s*[:\-]?\s*(\S+)", raw)
    colis  = re.findall(r"(?i)(?:nombre\s*de\s*colis|nbr\s*colis|colis)\s*[:\-]?\s*(\d+)", raw)
    pieces = re.findall(r"(?i)(?:nombre\s*de\s*pi[eè]ces|pcs(?:\s*par\s*colis)?|pi[eè]ce?s?)\s*[:\-]?\s*(\d+)", raw)

    # On prend la longueur minimale pour zipper
    n = min(len(refs), len(colis), len(pieces))

    data = []
    for i in range(n):
        c = int(colis[i])
        p = int(pieces[i])
        data.append({
            "Référence": refs[i],
            "Nb de colis": c,
            "pcs par colis": p,
            "total": c * p,
            "Vérification": ""
        })

    # Si on n'a rien, on renvoie un tableau vide (tu peux ajouter un warning)
    if not data:
        return pd.DataFrame(columns=[
            "Référence","Nb de colis","pcs par colis","total","Vérification"
        ])
    return pd.DataFrame(data)
