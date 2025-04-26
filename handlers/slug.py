# helpers/slug.py
import unidecode
from common_order import REGIONS_AND_DISTRICTS

def slugify(text: str) -> str:
    """'Наманган ш.' → 'namangan_sh', 'Қўшработ' → 'qoshrabot'"""
    return (
        unidecode.unidecode(text)   # кирилл→латин
        .replace("'", "")           # ўзбек апострофларини ўчириш
        .replace(" ", "_")          # пробел → _
        .lower()
    )

# Бир марта сессия башида қурилади
REGION_TO_SLUG = {r: slugify(r) for r in REGIONS_AND_DISTRICTS}
SLUG_TO_REGION = {v: k for k, v in REGION_TO_SLUG.items()}

DISTRICT_TO_SLUG = {
    f"{r}.{d}": slugify(d) for r, ds in REGIONS_AND_DISTRICTS.items() for d in ds
}
SLUG_TO_DISTRICT = {v: k.split(".", 1)[1] for k, v in DISTRICT_TO_SLUG.items()}
