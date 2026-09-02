"""Single in-memory representation of a design-space sweep group.

A Spec is whatever `gen_models.cartesian_exec` actually reads: an input size
range, a per-layer size range, a bitwidth list and an activation mask. Those
four fields alone determine the `dense_{N}l_{idx}` stem of every design in the
group (see enumerate_space.py), so they are the only things a sweep definition
is allowed to carry across the JSON -> TSV migration.

Two loaders produce the same Spec:

  spec_from_json(path)      legacy configs/model_sweeps/*.json
  spec_from_row(row)        a row of slurm/sweeps.tsv

and `to_gen_model_config()` renders a Spec back to the dict that
`iter_manager_catapult.py --gen_model_config_json` expects, so the new catalog
drives the unmodified generator.
"""

import json
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# Fixed order that gen_models._active_activations() filters — NOT alphabetical,
# and NOT the ["relu", "sigmoid", "tanh"] order the LHS samplers use. Changing
# it renumbers every stem.
ACTIVATION_NAMES = ["relu", "tanh", "sigmoid", "softmax"]

TECHS = {
    "nangate45": {
        "asiclibs": "nangate-45nm_beh",
        "startup": "",
    },
    "gf22": {
        "asiclibs": "GF22FDX_SC8T_104CPP_BASE_CSC24R_TT_0P90V_0P00V_0P00V_0P00V_25C_dc",
        "startup": "/global/homes/g/gdg/research/projects/genesis/gf22nm-lib/libsetup.tcl",
    },
}


@dataclass
class Spec:
    group: str
    tech: str
    input_range: Tuple[int, int]
    layers: List[Tuple[int, int]]
    bitwidths: List[int]
    activations: List[str]
    rf: List[int] = field(default_factory=lambda: [16])
    mode: str = "cartesian"
    candidates: Optional[str] = None
    weight_int_width: int = 2
    activ_int_width: int = 2
    # Basename (without 'config_' / '.json') of the model-sweep JSON this row
    # replaces. It is the key slurm/tests/check_design_space.py joins on, and the
    # audit trail from the catalog back to the archived runs.
    legacy: Optional[str] = None
    notes: str = ""

    @property
    def n_layers(self) -> int:
        return len(self.layers)

    def activation_mask(self) -> List[int]:
        return [1 if n in self.activations else 0 for n in ACTIVATION_NAMES]

    def to_gen_model_config(self) -> dict:
        """Render back to the schema gen_models.cartesian_exec consumes."""
        return {
            "input_lb": self.input_range[0],
            "input_ub": self.input_range[1],
            "layers": [{"size_lb": lb, "size_ub": ub} for lb, ub in self.layers],
            "bitwidths": list(self.bitwidths),
            "weight_int_width": self.weight_int_width,
            "activ_int_width": self.activ_int_width,
            "probs": {"activations": self.activation_mask()},
        }

    def flow_overrides(self, rf: int) -> dict:
        """The 3 keys that used to be baked into 8 separate flow-config files."""
        return {"default_reuse_factor": int(rf), **TECHS[self.tech]}


def dense_sizes(lb: int, ub: int) -> List[int]:
    """Mirror of gen_models._dense_sizes()."""
    return [2 ** i for i in range(0, 20) if lb <= 2 ** i <= ub]


def spec_from_json(path: str, group: Optional[str] = None, tech: str = "nangate45") -> Spec:
    """Load a legacy configs/model_sweeps/*.json 'general mode' sweep."""
    with open(path) as f:
        cfg = json.load(f)

    if "layers" not in cfg:
        raise ValueError(f"{path}: legacy random-sampling schema, not a cartesian sweep")

    if "bitwidths" in cfg:
        bitwidths = list(cfg["bitwidths"])
    else:
        bitwidths = list(range(cfg["bitwidth_lb"], cfg["bitwidth_ub"] + 1, 2))

    activations = [
        name for name, p in zip(ACTIVATION_NAMES, cfg["probs"]["activations"]) if p > 0
    ]

    import os

    return Spec(
        group=group or os.path.basename(path)[len("config_") : -len(".json")],
        tech=tech,
        input_range=(cfg["input_lb"], cfg["input_ub"]),
        layers=[(l["size_lb"], l["size_ub"]) for l in cfg["layers"]],
        bitwidths=bitwidths,
        activations=activations,
        weight_int_width=cfg.get("weight_int_width", 1),
        activ_int_width=cfg.get("activ_int_width", 1),
    )


def _parse_range(text: str) -> Tuple[int, int]:
    lb, _, ub = text.partition("-")
    return int(lb), int(ub)


def _parse_int_list(text: str) -> List[int]:
    return [int(x) for x in text.split(",") if x]


def spec_from_row(row: dict) -> Spec:
    """Build a Spec from one parsed slurm/sweeps.tsv row."""
    layers = []
    for i in range(1, int(row["layers"]) + 1):
        cell = row[f"l{i}"]
        if cell in ("", "-"):
            raise ValueError(f"{row['group']}: missing l{i} for a {row['layers']}-layer sweep")
        layers.append(_parse_range(cell))

    return Spec(
        group=row["group"],
        tech=row["tech"],
        input_range=_parse_range(row["input"]),
        layers=layers,
        bitwidths=_parse_int_list(row["bitwidths"]),
        activations=[a for a in row["acts"].split(",") if a],
        rf=_parse_int_list(row["rf"]),
        mode=row.get("mode", "cartesian"),
        candidates=_optional(row.get("candidates")),
        legacy=_optional(row.get("legacy")),
        notes=row.get("notes", ""),
    )


def _optional(cell):
    """'' and '-' both mean 'not set' in the TSV."""
    return cell if cell not in (None, "", "-") else None


def load_catalog(path: str) -> dict:
    """Parse slurm/sweeps.tsv into {group: Spec}. '#' lines are comments."""
    specs = {}
    with open(path) as f:
        header = None
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            if line.startswith("#"):
                if header is None:
                    header = line.lstrip("#").split("\t")
                    header = [h.strip() for h in header]
                continue
            if header is None:
                raise ValueError(f"{path}: data row before the '#' header line")
            cells = line.split("\t")
            cells += [""] * (len(header) - len(cells))
            row = dict(zip(header, (c.strip() for c in cells)))
            specs[row["group"]] = spec_from_row(row)
    return specs
