# Pyrfume ingredient catalog and retrieval for fragrance grounding.
# Loads datasets filters non materials caches JSON and retrieves by brand query.
from __future__ import annotations
import ast
import json
import logging
import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize
from src.config import Settings
from src.models.descriptor import BrandAestheticDescriptor

logger = logging.getLogger(__name__)

# Extra query words taken from brand energy so retrieval tracks intensity.
ENERGY_INTENSITY_HINTS: dict[str, list[str]] = {
    "very_low": ["soft", "subtle", "delicate", "light", "transparent"],
    "low": ["gentle", "calm", "smooth", "quiet", "intimate"],
    "moderate": ["balanced", "rounded", "warm", "comfortable"],
    "high": ["bold", "vibrant", "bright", "energetic", "sparkling"],
    "very_high": ["intense", "powerful", "rich", "deep", "dramatic"],
}

# Odor class labels that must not be used as pyramid materials.
# These words are family names or adjectives rather than real ingredients.
GENERIC_DESCRIPTORS = frozenset(
    {
        "floral",
        "woody",
        "fresh",
        "green",
        "sweet",
        "fruity",
        "warm",
        "soft",
        "spicy",
        "aromatic",
        "balsamic",
        "earthy",
        "musky",
        "clean",
        "dry",
        "minty",
        "mint",
        "marine",
        "ozonic",
        "ozone",
        "herbal",
        "herbaceous",
        "powdery",
        "leafy",
        "cologne",
        "natural",
        "animal",
        "nutty",
        "metallic",
        "refreshing",
        "refreshing odor",
        "aldehydic",
        "fermented",
        "roasted",
        "citrus",
        "water",
        "watery",
        "cool",
        "weak",
        "burnt",
        "fatty",
        "creamy",
        "malty",
        "tropical",
        "phenolic",
        "sulfurous",
        "camphoreous",
        "caramellic",
        "mentholic",
        "naphthyl",
        "cortex",
        "absolute",
        "berry",
        "hay",
        "sawdust",
        "odor",
        "odour",
        "scent",
        "fragrance",
        # Common food like generics that behave like class labels.
        "honey",
        "chocolate",
        "tea",
        "apple",
        "onion",
        "coffee",
        "raisin",
        "cherry",
        "plum",
        "tropical-fruit",
    }
)
CAS_PATTERN = re.compile(r"^\d{2,7}-\d{2}-\d$")
NOTE_LIKE = re.compile(r"^[a-z][a-z0-9 /-]{1,40}$")
_ODOR_WORD = re.compile(r"\b(odor|odour|scent|fragrance|accord)\b")
_JUNK_REGISTRY_ID = re.compile(r"^(zinc|schembl|akos)\d+$", re.I)
_MATERIAL_HINT = re.compile(
    r"\b(oil|extract|otto|acetate|aldehyde|ketone|alcohol|oxide|ether|lactone|"
    r"nitrile|cinnamate|salicylate|benzoate|formate|eugenol|menthol|terpinene|"
    r"linalool|ionone|pyrrole|thiazoline)\b",
    re.I,
)
_STOP_TOKENS = frozenset({"a", "an", "the", "of", "and", "or", "like"})


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


# True when the string is an odor class label rather than a material.
def is_odor_class_label(name: str) -> bool:
    normalized = _normalize_name(name)
    if not normalized:
        return True
    if normalized in GENERIC_DESCRIPTORS:
        return True
    if _ODOR_WORD.search(normalized):
        return True
    return False


def _tokens(name: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9+]+", _normalize_name(name)) if token]


def is_junk_registry_id(name: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", _normalize_name(name))
    return bool(_JUNK_REGISTRY_ID.match(compact))


# Reject phrases that repeat the same content word.
def is_repeated_descriptor_phrase(name: str) -> bool:
    tokens = [token for token in _tokens(name) if token not in _STOP_TOKENS]
    if len(tokens) < 2:
        return False
    return len(tokens) != len(set(tokens))


# Reject adjective only phrases unless a material hint is present.
def is_adjective_only_phrase(name: str) -> bool:
    if _MATERIAL_HINT.search(name):
        return False
    tokens = [token for token in _tokens(name) if token not in _STOP_TOKENS]
    if not tokens:
        return True
    return all(token in GENERIC_DESCRIPTORS or token in _STOP_TOKENS for token in tokens)


# Display name currently equals the raw material name for cache compatibility.
def _derive_display_name(name: str, descriptors: tuple[str, ...] | None = None) -> str:
    return (name or "").strip()


@dataclass(frozen=True)
class IngredientRecord:
    name: str
    display_name: str
    descriptors: tuple[str, ...]
    sources: tuple[str, ...]
    cid: int | None = None

    @property
    def search_text(self) -> str:
        return " ".join([self.name, self.display_name, *self.descriptors]).lower()


@dataclass
class RetrievalResult:
    ingredients: list[IngredientRecord]
    query: str
    datasets: list[str]


# Whether a catalog row is safe to use as a fragrance material.
# Drop odor class labels and junk registry ids.
def is_selectable_ingredient(record: IngredientRecord) -> bool:
    labels = (record.name, record.display_name)
    if any(is_junk_registry_id(label) for label in labels):
        return False
    if CAS_PATTERN.match(record.display_name.strip()) and CAS_PATTERN.match(
        _normalize_name(record.name)
    ):
        return False
    if record.cid:
        return not is_odor_class_label(record.name)

    if any(is_odor_class_label(label) for label in labels):
        return False
    if any(is_repeated_descriptor_phrase(label) for label in labels):
        return False
    if any(is_adjective_only_phrase(label) for label in labels):
        return False
    if any(re.search(r"\blike\b", _normalize_name(label)) for label in labels):
        return False
    return True


def filter_material_records(records: list[IngredientRecord]) -> list[IngredientRecord]:
    return [record for record in records if is_selectable_ingredient(record)]


def _split_descriptors(raw: str) -> list[str]:
    parts = re.split(r"[;,/|]", raw.lower())
    return [part.strip() for part in parts if part.strip()]


# Parses descriptor cells from list literals or delimited strings.
def _parse_label_list(raw: object) -> list[str]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    if isinstance(raw, list):
        return [str(item).strip().lower() for item in raw if str(item).strip()]
    text = str(raw).strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = ast.literal_eval(text)
            if isinstance(parsed, list):
                return [str(item).strip().lower() for item in parsed if str(item).strip()]
        except (SyntaxError, ValueError):
            pass
    return _split_descriptors(text)


# Inserts or merges an ingredient into the in memory catalog by name.
def _merge_record(
    catalog: dict[str, IngredientRecord],
    name: str,
    descriptors: list[str],
    source: str,
    cid: int | None,
) -> None:
    normalized = _normalize_name(name)
    if not normalized or normalized in {"nan", "none"}:
        return
    if is_odor_class_label(name):
        return

    unique_descriptors = tuple(dict.fromkeys(d for d in descriptors if d))
    if normalized in catalog:
        existing = catalog[normalized]
        merged_descriptors = tuple(dict.fromkeys([*existing.descriptors, *unique_descriptors]))
        merged_sources = tuple(dict.fromkeys([*existing.sources, source]))
        catalog[normalized] = IngredientRecord(
            name=existing.name,
            display_name=_derive_display_name(existing.name, merged_descriptors),
            descriptors=merged_descriptors,
            sources=merged_sources,
            cid=existing.cid or cid,
        )
        return

    catalog[normalized] = IngredientRecord(
        name=name.strip(),
        display_name=_derive_display_name(name, unique_descriptors),
        descriptors=unique_descriptors,
        sources=(source,),
        cid=cid,
    )


def _load_goodscents(catalog: dict[str, IngredientRecord]) -> None:
    import pyrfume

    molecules = pyrfume.load_data("goodscents/molecules.csv")
    behavior = pyrfume.load_data("goodscents/behavior.csv")
    stimuli = pyrfume.load_data("goodscents/stimuli.csv")

    cid_to_name: dict[int, str] = {}
    for cid, row in molecules.iterrows():
        cid_to_name[int(cid)] = str(row["name"])

    for stimulus, row in behavior.iterrows():
        descriptors = _split_descriptors(str(row["Descriptors"]))
        cid = None
        name = str(stimulus)

        if stimulus in stimuli.index:
            cid_value = stimuli.loc[stimulus, "CID"]
            if not np.isnan(cid_value):
                cid = int(cid_value)
        elif str(stimulus).isdigit():
            cid = int(stimulus)

        if cid is None or cid not in cid_to_name:
            continue
        name = cid_to_name[cid]
        _merge_record(catalog, name, descriptors, "goodscents", cid)


def _load_leffingwell(catalog: dict[str, IngredientRecord]) -> None:
    import pyrfume

    molecules = pyrfume.load_data("leffingwell/molecules.csv")
    behavior = pyrfume.load_data("leffingwell/behavior_sparse.csv")
    stimuli = pyrfume.load_data("leffingwell/stimuli.csv")

    cid_to_name: dict[int, str] = {}
    for cid, row in molecules.iterrows():
        cid_to_name[int(cid)] = str(row["name"])

    for stimulus, row in behavior.iterrows():
        descriptors = _parse_label_list(row.get("Labels"))
        raw_labels = str(row.get("Raw Labels", "")).strip()
        if raw_labels and raw_labels.lower() not in {"nan", "none"}:
            descriptors = list(dict.fromkeys([*descriptors, *_split_descriptors(raw_labels)]))

        cid = None
        if stimulus in stimuli.index:
            cid_value = stimuli.loc[stimulus, "CID"]
            if cid_value is not None and not (isinstance(cid_value, float) and np.isnan(cid_value)):
                cid = int(cid_value)

        if cid is None or cid <= 0 or cid not in cid_to_name:
            continue
        name = cid_to_name[cid]
        _merge_record(catalog, name, descriptors, "leffingwell", cid)


def _load_ifra(catalog: dict[str, IngredientRecord]) -> None:
    import pyrfume

    molecules = pyrfume.load_data("ifra_2019/molecules.csv")
    behavior = pyrfume.load_data("ifra_2019/behavior.csv")

    for stimulus, row in behavior.iterrows():
        descriptors = [
            str(row[col]).strip().lower()
            for col in ("Descriptor 1", "Descriptor 2", "Descriptor 3")
            if str(row[col]).strip().lower() not in {"", "nan", "none"}
        ]
        cid = int(stimulus) if str(stimulus).lstrip("-").isdigit() else None
        if cid is None or cid not in molecules.index:
            continue
        name = str(molecules.loc[cid, "name"])
        _merge_record(catalog, name, descriptors, "ifra_2019", cid)


# Builds a filtered sorted catalog from the requested Pyrfume datasets.
def build_catalog(datasets: list[str] | None = None) -> list[IngredientRecord]:
    datasets = datasets or ["goodscents", "leffingwell", "ifra_2019"]
    catalog: dict[str, IngredientRecord] = {}

    loaders = {
        "goodscents": _load_goodscents,
        "leffingwell": _load_leffingwell,
        "ifra_2019": _load_ifra,
    }

    for dataset in datasets:
        loader = loaders.get(dataset)
        if loader is None:
            logger.warning("Unknown Pyrfume dataset: %s", dataset)
            continue
        logger.info("Loading Pyrfume dataset: %s", dataset)
        loader(catalog)

    records = filter_material_records(
        sorted(catalog.values(), key=lambda record: record.name.lower())
    )
    logger.info("Built Pyrfume catalog with %d unique ingredients", len(records))
    return records


def save_catalog_cache(records: list[IngredientRecord], path: str | Path) -> None:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(record) for record in records]
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_catalog_cache(path: str | Path) -> list[IngredientRecord] | None:
    cache_path = Path(path)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Invalid Pyrfume catalog cache at %s", cache_path)
        return None

    loaded = [
        IngredientRecord(
            name=item["name"],
            display_name=(item.get("name") or "").strip(),
            descriptors=tuple(item.get("descriptors", [])),
            sources=tuple(item.get("sources", [])),
            cid=item.get("cid"),
        )
        for item in payload
    ]
    return filter_material_records(loaded)


# Builds a free text retrieval query from brand descriptor fields.
def build_query(bad: BrandAestheticDescriptor) -> str:
    terms: list[str] = [
        bad.brand_item or "",
        *bad.mood,
        *bad.texture,
        *bad.visual_style,
        *bad.colours,
        *bad.sensory_metaphors,
        *ENERGY_INTENSITY_HINTS.get(bad.energy.value, []),
        bad.color_temperature.value,
        bad.narrative,
    ]
    return " ".join(term.strip().lower() for term in terms if term and str(term).strip())


def display_key(record: IngredientRecord) -> str:
    return record.display_name.strip().lower()


# Short comma joined odor tags for model context lines.
def smell_blurb(record: IngredientRecord, limit: int = 6) -> str:
    return ", ".join(record.descriptors[:limit]) or "no smell tags"


# Walks ranked neighbors deduplicates names and stops at the requested count.
def _dedupe_top_k(
    records: list[IngredientRecord],
    ranked_indices: np.ndarray,
    top_k: int,
    *,
    keep_index: Callable[[int], bool] | None = None,
) -> list[IngredientRecord]:
    results: list[IngredientRecord] = []
    seen: set[str] = set()
    for index in ranked_indices:
        if keep_index is not None and not keep_index(int(index)):
            continue
        record = records[int(index)]
        key = display_key(record)
        if key in seen:
            continue
        seen.add(key)
        results.append(record)
        if len(results) >= top_k:
            break
    return results


class _BaseCatalogRetriever:
    # Shared helper that retrieves ingredients for a brand descriptor.

    records: list[IngredientRecord]
    backend_name: str = "lsa_knn"

    def retrieve(self, query: str, top_k: int = 30) -> list[IngredientRecord]:
        raise NotImplementedError

    def retrieve_for_profile(
        self,
        bad: BrandAestheticDescriptor,
        top_k: int = 30,
        datasets: list[str] | None = None,
    ) -> RetrievalResult:
        query = build_query(bad)
        results = self.retrieve(query, top_k=top_k)
        results = filter_material_records(results)
        if datasets:
            allowed = set(datasets)
            results = [
                record
                for record in results
                if any(source in allowed for source in record.sources)
            ]
        return RetrievalResult(
            ingredients=results,
            query=query,
            datasets=sorted({source for record in results for source in record.sources}),
        )


# Retrieves ingredients with LSA nearest neighbor search over odor text.
class LsaKnnRetriever(_BaseCatalogRetriever):
    backend_name = "lsa_knn"

    def __init__(self, records: list[IngredientRecord], n_components: int = 128):
        self.records = records
        self._vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=1,
        )
        corpus = [record.search_text for record in records]
        tfidf = self._vectorizer.fit_transform(corpus)
        n_docs, n_terms = tfidf.shape
        components = max(2, min(n_components, n_docs - 1, n_terms - 1))
        self._svd = TruncatedSVD(n_components=components, random_state=42)
        dense = self._svd.fit_transform(tfidf)
        self._matrix = normalize(dense)
        self._nn = NearestNeighbors(metric="cosine", algorithm="brute")
        self._nn.fit(self._matrix)

    def retrieve(self, query: str, top_k: int = 30) -> list[IngredientRecord]:
        if not self.records or not query.strip():
            return []

        query_tfidf = self._vectorizer.transform([query.lower()])
        query_vec = normalize(self._svd.transform(query_tfidf))
        neighbor_count = min(max(top_k * 4, top_k), len(self.records))
        _distances, indices = self._nn.kneighbors(query_vec, n_neighbors=neighbor_count)
        return _dedupe_top_k(self.records, indices.flatten(), top_k)


def make_retriever(records: list[IngredientRecord]) -> LsaKnnRetriever:
    materials = filter_material_records(records)
    if not materials:
        raise ValueError("Pyrfume catalog has no selectable materials after odor-label filter")
    return LsaKnnRetriever(materials)


# Loads or builds the catalog and returns a cached retriever.
# Prefer the shipped catalog file and only download Pyrfume if it is missing.
@lru_cache(maxsize=4)
def get_pyrfume_retriever(
    cache_path: str,
    datasets_key: str,
    material_filter_version: str = "v4",
) -> LsaKnnRetriever:
    settings = Settings()
    path = Path(cache_path)
    datasets = datasets_key.split(",") if datasets_key else settings.pyrfume_datasets

    records = load_catalog_cache(path)
    if records is None:
        records = build_catalog(datasets)
        save_catalog_cache(records, path)

    if not records:
        raise RuntimeError("Pyrfume catalog is empty — check dataset availability")

    return make_retriever(records)


# Public entry that retrieves top materials for a brand descriptor.
def retrieve_ingredients(
    bad: BrandAestheticDescriptor,
    settings: Settings | None = None,
) -> RetrievalResult:
    settings = settings or Settings()
    retriever = get_pyrfume_retriever(
        settings.pyrfume_catalog_cache_path,
        ",".join(settings.pyrfume_datasets),
    )
    return retriever.retrieve_for_profile(
        bad,
        top_k=settings.pyrfume_retrieval_top_k,
        datasets=settings.pyrfume_datasets,
    )


# Formats retrieval hits as context text for the fragrance model.
def format_retrieval_context(result: RetrievalResult) -> str:
    if not result.ingredients:
        return "No Pyrfume ingredients retrieved."

    lines = [
        "Retrieved real perfumery materials from Pyrfume (GoodScents, Leffingwell, IFRA).",
        "Each line is odor (what a person smells) then chemical (Pyrfume molecule name).",
        "Put only the chemical name in top/heart/base notes. Put the odor in note_guide.smells_like.",
        f"Retrieval query: {result.query}",
        "",
    ]
    for index, ingredient in enumerate(result.ingredients, start=1):
        odor = smell_blurb(ingredient) or "no odor tags"
        lines.append(
            f"{index}. smells like: {odor} — chemical: {ingredient.name}"
        )
    return "\n".join(lines)
