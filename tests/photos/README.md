# Physical photo dataset (PHYSICAL_CAPTURE)

88 photos of the 8 printed QualityRelay specimens (4 slots, 4 tabs), taken with our camera from straight above on a fixed white background.

One folder per specimen, named by role and design width: `slot/<role><width>mm/` and `tab/<role><width>mm/`.

| Folder | Specimen | Design width |
|---|---|---:|
| `slot/good2120mm/` | S-GOOD | 21.20 mm |
| `slot/normal2100mm/` | S-NOM | 21.00 mm |
| `slot/risk2070mm/` | S-RISK | 20.70 mm |
| `slot/defect1940mm/` | S-DEF (wrong size) | 19.40 mm |
| `tab/good1980mm/` | T-GOOD | 19.80 mm |
| `tab/normal2000mm/` | T-NOM | 20.00 mm |
| `tab/risk2030mm/` | T-RISK | 20.30 mm |
| `tab/defect2160mm/` | T-DEF (wrong size) | 21.60 mm |

Each folder holds:

| File | Contents |
|---|---|
| `snapshot-<timestamp>.png` (10 per specimen) | training photos |
| `measure.png` | the specimen next to the 20 mm ArUco marker, with the caliper reading |

Specimen IDs match the caliper measurement log. Design widths are listed in [`examples/cad/print_manifest.csv`](../../examples/cad/print_manifest.csv).
