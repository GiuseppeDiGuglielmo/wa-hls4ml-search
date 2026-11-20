# Provenance: catalog group → archived data → the script that used to run it

## Why this file exists

Every archived design in `/global/cfs/cdirs/amsc011/shared/wa-hls4ml-catapult/` was produced
by a one-off campaign script under `slurm/examples/`. Those 49 scripts were replaced by one
entry point (`slurm/sweep.sh`) plus one catalog row per group (`slurm/sweeps.tsv`), and then
deleted. The shared archive's own `README.md` indexes runs by design-space **group name**, not
by the script that generated them, so without this file the link from a run directory back to
the thing that produced it would be lost at the moment the scripts went away.

The mapping below was established on 2026-09-01 by cross-referencing script output directories
and design counts against the shared archive README, then re-verified on 2026-09-02 against
every run's `source_dir.txt`, which records the original scratch path and is therefore direct
evidence rather than inference.

**Rule going forward:** a new campaign is a new row in `slurm/sweeps.tsv`, and a new row here
once its runs are archived. Never edit an existing catalog row — a design's stem is
`dense_{N}l_{idx}`, its index in the cartesian product of that row's columns, so editing a row
renumbers designs that are already archived and silently breaks the `(run, stem)` join keys.
`python slurm/tests/check_design_space.py` enforces this.

Deleted scripts remain in git history; `git log --diff-filter=D --name-only` finds them.

## Legend

- ✅ **complete** — archived design count matches the group's target exactly.
- ⚠️ **incomplete / unusable** — see the note.
- 🔧 **live tool** — re-run on demand, never archived.

---

## Group 1 — 3-layer cartesian, sz64 groups

Was: `run_dense_3layers_sz64_{l1,l2,l3,inp}.sh` plus the `_node_a/b/c` and `_node_d/e` variants
(9 scripts) over `common/dense_group_batch.sh`. The `_node_*` scripts were alternate submission
paths for the *same* RF batches — they land in the same run directories, not separate ones, and
are now `sweep.sh --nodes`. Archive root: `nangate45/`.

| Catalog group | RF | Archived run directory | Designs | Status |
|---|---|---|---|---|
| `3l_sz64_l3` | 1  | `run_20260522_214453_7dd5508f` | 10,368 | ✅ |
| `3l_sz64_l3` | 4  | `run_20260524_141002_d30e0a91` | 10,368 | ✅ |
| `3l_sz64_l3` | 8  | `run_20260525_095507_5d107c91` | 10,368 | ✅ |
| `3l_sz64_l3` | 16 | `run_20260526_025959_d64af1bb` | 10,368 | ✅ |
| `3l_sz64_l2` | 1  | `run_20260527_074357_aff0d65c` | 12,960 | ✅ |
| `3l_sz64_l2` | 4  | `run_20260528_121757_f758fd3a` | 12,960 | ✅ |
| `3l_sz64_l2` | 8  | `run_20260529_131718_42b83b2b` | 12,960 | ✅ |
| `3l_sz64_l2` | 16 | `run_20260530_130622_1329d506` | 12,960 | ✅ |
| `3l_sz64_l1` | 1  | `run_20260531_093401_e6edde98` | 16,200 | ✅ |
| `3l_sz64_l1` | 4  | `run_20260601_090902_4db63227` | 16,200 | ✅ |
| `3l_sz64_l1` | 8  | `run_20260601_091721_d8d2e774` | 16,200 | ✅ |
| `3l_sz64_l1` | 16 | `run_20260602_175454_3852b272` | 16,200 | ✅ |
| `3l_sz64_inp_l1a` | 1  | `run_20260603_083059_83e7d4d3` | 16,200 | ✅ |
| `3l_sz64_inp_l1a` | 4  | `run_20260603_083059_aef76e2f` | 16,200 | ✅ |
| `3l_sz64_inp_l1a` | 8  | `run_20260605_031557_3b90ed92` | 16,200 | ✅ |
| `3l_sz64_inp_l1a` | 16 | `run_20260605_143602_67b69911` | 16,200 | ✅ |
| `3l_sz64_inp_l1b` | 1  | `run_20260604_200216_be9fcdf2` | 4,050  | ✅ |
| `3l_sz64_inp_l1b` | 4  | `run_20260604_173538_d4da9e4b` | 4,050  | ✅ |
| `3l_sz64_inp_l1b` | 8  | `run_20260606_035812_ad8aa3ed` | 4,050  | ✅ |
| `3l_sz64_inp_l1b` | 16 | `run_20260607_130139_249819c5` | 4,050  | ✅ |

All 20 runs (5 groups × 4 RF) accounted for. **Complete.**

## Group 2 — 3-layer cartesian, base and sz32 groups

Was: `run_dense_3layers_cartesian_{rf1,bw6_10_14,rf_sweep,bw6_10_14_rf_sweep}.sh`, the ten
`run_dense_3layers_cartesian_part_{01..10}.sh` slices over `common/submit_cartesian_part.sh`,
and the sz32 family (`run_dense_3layers_sz32_extension.sh`, `_remaining.sh`, `_l3_rf4_8_16.sh`,
`restart_dense_3layers_sz32_from_rf8.sh`, `resume_dense_3layers_sz32.sh`). The ten `part_*`
scripts submitted non-overlapping array slices of a *single* run, and the sz32
restart/resume/remaining scripts were recovery paths into the same run directories, not extra
campaigns. Archive root: `nangate45/`.

| Catalog group | RF | Archived run directory | Designs |
|---|---|---|---|
| `3l_base`      | 1  | `run_20260511_183550_fb022142` |  6,561 |
| `3l_base`      | 4  | `run_20260512_151951_191a56e5` |  6,561 |
| `3l_base`      | 8  | `run_20260512_200911_b5360c99` |  6,561 |
| `3l_base`      | 16 | `run_20260513_012331_495070b6` |  6,561 |
| `3l_bw61014`   | 1  | `run_20260512_100539_843189bc` |  6,561 |
| `3l_bw61014`   | 4  | `run_20260513_075310_b7091470` |  6,561 |
| `3l_bw61014`   | 8  | `run_20260513_143630_6f921598` |  6,561 |
| `3l_bw61014`   | 16 | `run_20260513_220413_553f3193` |  6,561 |
| `3l_sz32_inp`  | 1, 4, 8, 16 | `run_20260514_150548_10d8cee9`, `run_20260514_235659_91548b87`, `run_20260516_222810_95296af7`, `run_20260517_060358_bf65649b` | 10,368 each |
| `3l_sz32_l1`   | 1, 4, 8, 16 | `run_20260517_141021_9070d30b`, `run_20260517_212712_61b39519`, `run_20260518_030141_00157288`, `run_20260518_100543_e3efd747` |  7,776 each |
| `3l_sz32_l2`   | 1, 4, 8, 16 | `run_20260518_174935_95663e33`, `run_20260518_225022_45120a12`, `run_20260519_081546_edbd2e1b`, `run_20260519_173328_b70ff212` |  5,832 each |
| `3l_sz32_l3`   | 1, 4, 8, 16 | `run_20260520_003252_1f6510ac`, `run_20260521_085618_19b6d94f`, `run_20260521_140624_5cdffafb`, `run_20260521_193026_cba4319e` |  4,374 each |

Together with group 1 these are the 44 runs of the 405,000-design 3-layer cartesian sweep,
which the shared archive README reports as "verified: 0 missing, 0 duplicates". **Complete.**

### 3-layer reports from reruns, tarballs from the first attempt

Found on 2026-11-19 by comparing each archived report's `Config.OutputDir` with the run it
is archived in. In 19 of the 44 runs, 3,490 designs (0.9% of the 405,000) have a report
written by a later rerun (`*_rerun`, `*_rerun2` and `rerun_rf*_rerun2` folders from June
2026), while their tarball is still the run's first attempt. The QoR in those reports comes
from a synthesis that succeeded, so the labels are valid. The tarballs do not match them:

- 3,172 tarballs hold a complete first attempt (all 13 Catapult steps).
- 165 stopped partway, for example at `go compile: Too many real operations` after 5 s
  (`run_20260521_193026_cba4319e/dense_3l_1645`).
- 153 hold no Catapult `messages.txt`.

The reruns' own projects cannot replace them: their scratch `tarballs/` folders are empty and
the scratch purge has removed the Catapult logs from their `build/` folders. Catapult time
read from these tarballs (`make design-cost`) counts the first attempt only, so it is low for
these designs, by roughly 320 h over all of them.

`slurm/report_tarball_mismatch.tsv` lists every such design: run, stem, the scratch folder
the report came from, and the number of Catapult steps in the archived tarball (`-` when the
tarball could not be read).

| Archived run | Designs | Report written in |
|---|---|---|
| `run_20260521_193026_cba4319e` | 212 | `catapult_dense_3layers_sz32_l3_rf16_rerun2/run_20260605_000437_90ec3b44` |
| `run_20260522_214453_7dd5508f` | 459 | `catapult_dense_3layers_sz64_l3_rf1_rerun2/run_20260604_195728_91a8b4b2` |
| `run_20260524_141002_d30e0a91` |  69 | `catapult_dense_3layers_sz64_l3_rf4_rerun2/run_20260604_153843_bf273809` |
| `run_20260525_095507_5d107c91` |  44 | `catapult_dense_3layers_sz64_l3_rf8_rerun2/run_20260604_122348_ca1f4262` |
| `run_20260526_025959_d64af1bb` |  14 | `catapult_dense_3layers_sz64_l3_rf16_rerun2/run_20260604_111248_609e1dfb` |
| `run_20260527_074357_aff0d65c` | 333 | `catapult_dense_3layers_sz64_l2_rf1_rerun2/run_20260604_210013_79e08b2d` |
| `run_20260528_121757_f758fd3a` | 235 | `catapult_dense_3layers_sz64_l2_rf4_rerun2/run_20260604_230504_cc3b3596` |
| `run_20260529_131718_42b83b2b` | 136 | `catapult_dense_3layers_sz64_l2_rf8_rerun2/run_20260605_020910_bfe7de6c` |
| `run_20260530_130622_1329d506` | 147 | `catapult_dense_3layers_sz64_l2_rf16_rerun2/run_20260605_013951_c9d8aee2` |
| `run_20260531_093401_e6edde98` | 503 | `catapult_dense_3layers_sz64_l1_rf1_rerun2/run_20260604_180916_9fe9d367` |
| `run_20260601_090902_4db63227` | 251 | `catapult_dense_3layers_sz64_l1_rf4_rerun2/run_20260604_221427_f67625d1` |
| `run_20260601_091721_d8d2e774` | 186 | `catapult_dense_3layers_sz64_l1_rf8_rerun2/run_20260605_005925_117bea94` |
| `run_20260602_175454_3852b272` | 104 | `catapult_dense_3layers_sz64_l1_rf16_rerun2/run_20260604_173353_99715f12` |
| `run_20260603_083059_83e7d4d3` | 165 | `rerun_rf1_rerun2/run_20260605_085420_12434cd5` |
| `run_20260603_083059_aef76e2f` |  99 | `rerun_rf4_rerun2/run_20260605_094145_e15c20cf` |
| `run_20260604_173538_d4da9e4b` |  19 | `rerun_rf4_rerun2/run_20260605_101927_5941871b` |
| `run_20260604_200216_be9fcdf2` | 228 | `catapult_dense_3layers_sz64_inp_rf1_l1b_rerun/run_20260608_102938_bc24f230` |
| `run_20260605_031557_3b90ed92` | 160 | `catapult_dense_3layers_sz64_inp_rf8_l1a_rerun/run_20260608_132918_2d0b54c7` |
| `run_20260605_143602_67b69911` | 126 | `catapult_dense_3layers_sz64_inp_rf16_l1a_rerun/run_20260608_165001_efaa5d01` |

### 3-layer tarballs that cannot be read

Found on 2026-11-19 with `make design-cost` over every dataset design. 60 archived 3-layer
tarballs, in 15 of the runs above, cannot be opened: 56 are cut short (gzip ends early,
`EOFError`) and 4 are empty files (`ReadError`). Their reports are complete and come from
the run itself, so the QoR is valid; only the project and its Catapult time are missing.
None of them has an intact copy in the run's scratch folder (`source_dir.txt`).

| Archived run | Tarballs | Designs |
|---|---|---|
| `run_20260522_214453_7dd5508f` | 1 | `dense_3l_3122` |
| `run_20260524_141002_d30e0a91` | 5 | `dense_3l_3952`, `dense_3l_7094`, `dense_3l_7095`, `dense_3l_7096`, `dense_3l_7104` |
| `run_20260526_025959_d64af1bb` | 2 | `dense_3l_3669`, `dense_3l_3683` (empty) |
| `run_20260527_074357_aff0d65c` | 5 | `dense_3l_5817`, `dense_3l_5872`, `dense_3l_5873`, `dense_3l_10915`, `dense_3l_10919` |
| `run_20260528_121757_f758fd3a` | 3 | `dense_3l_6042`, `dense_3l_12586`, `dense_3l_12639` |
| `run_20260529_131718_42b83b2b` | 4 | `dense_3l_3208`, `dense_3l_7668`, `dense_3l_7673`, `dense_3l_11591` |
| `run_20260530_130622_1329d506` | 5 | `dense_3l_2953`, `dense_3l_2973`, `dense_3l_2982`, `dense_3l_2988`, `dense_3l_8520` |
| `run_20260531_093401_e6edde98` | 7 | `dense_3l_6459`, `dense_3l_6462`, `dense_3l_13612`, `dense_3l_13613`, `dense_3l_13619` (empty), `dense_3l_15990`, `dense_3l_15991` |
| `run_20260601_091721_d8d2e774` | 5 | `dense_3l_2671`, `dense_3l_7269`, `dense_3l_7277`, `dense_3l_12273`, `dense_3l_12278` |
| `run_20260602_175454_3852b272` | 3 | `dense_3l_3377`, `dense_3l_3383`, `dense_3l_7545` |
| `run_20260603_083059_83e7d4d3` | 3 | `dense_3l_3585`, `dense_3l_3695`, `dense_3l_14464` |
| `run_20260603_083059_aef76e2f` | 7 | `dense_3l_9286`, `dense_3l_9287`, `dense_3l_9288`, `dense_3l_15645`, `dense_3l_15647`, `dense_3l_15648` (empty), `dense_3l_15675` |
| `run_20260604_200216_be9fcdf2` | 1 | `dense_3l_2707` |
| `run_20260605_031557_3b90ed92` | 2 | `dense_3l_9332`, `dense_3l_13073` |
| `run_20260605_143602_67b69911` | 7 | `dense_3l_4490`, `dense_3l_4491` (empty), `dense_3l_4496`, `dense_3l_8188`, `dense_3l_8189`, `dense_3l_8214`, `dense_3l_15416` |

## Group 3 — 2-layer cartesian family

Was: eight `run_dense_2layers_cartesian*.sh` scripts over `common/dense2layer_cartesian.sh`.
The A/B/C sub-runs are three disjoint slices of the size-64 space and remain three catalog
rows. Archive root: `nangate45/`.

| Catalog group | RF | Archived run directory | Designs |
|---|---|---|---|
| `2l_base`             | 16 | `run_20260507_160021_89f04028` | 1,728 |
| `2l_base`             | 1  | `run_20260509_104324_11e5e751` | 1,728 |
| `2l_base`             | 4  | `run_20260509_120109_f8094eb6` | 1,728 |
| `2l_base`             | 8  | `run_20260509_131056_caebbb47` | 1,728 |
| `2l_bw61014`          | 16 | `run_20260508_154446_c18f8eb3` | 1,728 |
| `2l_bw61014`          | 1  | `run_20260510_154528_c8917edd` | 1,728 |
| `2l_bw61014`          | 4  | `run_20260510_165654_f30c3033` | 1,728 |
| `2l_bw61014`          | 8  | `run_20260510_180319_ebd4cdd3` | 1,728 |
| `2l_sz64_a`           | 16 | `run_20260508_184158_46e9dd55` |   675 |
| `2l_sz64_b`           | 16 | `run_20260508_192106_4dedc7d6` |   540 |
| `2l_sz64_c`           | 16 | `run_20260508_194842_4b715b4f` |   432 |
| `2l_sz64_bw61014_a`   | 16 | `run_20260508_204435_b1b9047b` |   675 |
| `2l_sz64_bw61014_b`   | 16 | `run_20260508_211850_f3a8e530` |   540 |
| `2l_sz64_bw61014_c`   | 16 | `run_20260508_214657_32dd8351` |   432 |
| `2l_sz64_a`           | 1, 4, 8 | `run_20260510_204739_13c1a819`, `run_20260510_230537_cf5febb5`, `run_20260511_003921_426134cf` | 675 each |
| `2l_sz64_b`           | 1, 4, 8 | `run_20260510_214441_14c8934c`, `run_20260510_234014_bcb31e78`, `run_20260511_011334_59ffdb74` | 540 each |
| `2l_sz64_c`           | 1, 4, 8 | `run_20260510_223408_33919b31`, `run_20260511_001619_9d10a1ce`, `run_20260511_014542_524c7288` | 432 each |
| `2l_sz64_bw61014_a`   | 1, 4, 8 | `run_20260511_060805_4e02e2de`, `run_20260511_083901_6a60a8b5`, `run_20260511_143622_0201a097` | 675 each |
| `2l_sz64_bw61014_b`   | 1, 4, 8 | `run_20260511_071014_a10ba85b`, `run_20260511_092924_36d66fe0`, `run_20260511_151257_48fb73c3` | 540 each |
| `2l_sz64_bw61014_c`   | 1, 4, 8 | `run_20260511_080843_6a6e4e7e`, `run_20260511_135215_270f6cde`, `run_20260511_153709_f0f0fd41` | 432 each |

All 32 runs accounted for (the README's "0 missing, 0 duplicates across all 32 runs",
27,000 designs). **Complete.**

## Group 4 — single-layer cartesian

Was: `run_dense_single_layer_cartesian.sh`, `_bw14.sh`, `_rf_sweep.sh`. Archive root:
`nangate45/`.

| Catalog group | RF | Archived run directory | Designs |
|---|---|---|---|
| `1l_base` | 1  | `run_20260514_080438_d517ccc3` | 375 |
| `1l_base` | 4  | `run_20260514_084409_ecbede5f` | 375 |
| `1l_base` | 8  | `run_20260514_092503_5a04a419` | 375 |
| `1l_base` | 16 | `run_20260507_150243_e6c8c415` | 375 |
| `1l_bw14` | 1  | `run_20260514_105801_0cce2a70` |  75 |
| `1l_bw14` | 4  | `run_20260514_111447_70b7b78d` |  75 |
| `1l_bw14` | 8  | `run_20260514_112722_3075e6b2` |  75 |
| `1l_bw14` | 16 | `run_20260514_122808_3cb8e3c2` |  75 |

⚠️ `run_20260507_143427_1450d680` (240 designs, RF=16) is an early partial of `1l_base`,
superseded by the run above it and excluded from training. 1,800 designs. **Complete.**

## Group 5 — GF22FDX (22 nm)

Was: `run_dense_1layer_gf22_cartesian.sh` and `submit_gf22_nlayer_lhs.sh`. Archive root:
`gf22fdx/`. The LHS groups sample the 45nm archive and re-synthesise the identical networks in
GF22, so their design lists live in the archive as candidates files — **do not delete those**,
they are the only record of which architectures each pass covered.

| Catalog group | RF | Archived run directory | Designs | Status |
|---|---|---|---|---|
| `gf22_1l_base`  | 1  | `run_20260605_153705_3eede5d2` | 375 | ✅ |
| `gf22_1l_base`  | 4  | `run_20260605_160459_768f8700` | 375 | ✅ |
| `gf22_1l_base`  | 8  | `run_20260605_162710_115f4e59` | 375 | ✅ |
| `gf22_1l_base`  | 16 | `run_20260605_164648_431eef4c` | 375 | ✅ |
| `gf22_1l_bw14`  | 1  | `run_20260605_170515_79e74653` |  75 | ✅ |
| `gf22_1l_bw14`  | 4  | `run_20260605_172242_619c69dd` |  75 | ✅ |
| `gf22_1l_bw14`  | 8  | `run_20260605_173430_7d28cbde` |  75 | ✅ |
| `gf22_1l_bw14`  | 16 | `run_20260605_174449_e7017539` |  75 | ✅ |
| *(2-layer pass 1)* | 1, 4, 8, 16 | `run_20260606_223032_051bd1fc`, `run_20260606_232045_8ac3bd56`, `run_20260607_001449_e2fa9584`, `run_20260607_012313_0bcffe08` | 769 each | ⚠️ |
| `gf22_lhs_2l`   | 1  | `run_20260607_100135_5c007969` | 1,063 | ✅ |
| `gf22_lhs_2l`   | 4  | `run_20260607_114350_0c9e19ed` | 1,063 | ✅ |
| `gf22_lhs_2l`   | 8  | `run_20260607_124520_1441e498` | 1,063 | ✅ |
| `gf22_lhs_2l`   | 16 | `run_20260607_134420_9b44e235` | 1,063 | ✅ |
| `gf22_lhs_3l_p1`| 1  | `run_20260609_100326_75e83e4c` |   495 | ✅ |
| `gf22_lhs_3l_p1`| 16 | `run_20260609_104049_9d553287` |   495 | ✅ |
| `gf22_lhs_3l`   | 1  | `run_20260609_191425_587221e3` | 8,371 | ✅ |
| `gf22_lhs_3l`   | 4  | `run_20260610_015716_579c576a` | 8,371 | ✅ |
| `gf22_lhs_3l`   | 8  | `run_20260610_090535_3002071d` | 8,371 | ✅ |
| `gf22_lhs_3l`   | 16 | `run_20260610_153144_6b9ac5fb` | 8,371 | ✅ |

⚠️ **2-layer pass 1** has no catalog row: its candidates file was overwritten by pass 2 and no
longer exists, so it is not reproducible. Its coverage is also restricted — the sampler
deduplicated by stem name rather than by `(run, stem)` pair and so missed bitwidths 6, 10, 14
and size 64. The results are valid; use them knowing the parameter space is partial.

⚠️ **Empty ghost runs** — `run_20260606_203554_855c8660` (RF=1), `run_20260606_204655_feeb9a79`
(RF=4), `run_20260606_205745_4cd92899` (RF=8), `run_20260606_211113_92ff518d` (RF=16) hold 0
tarballs. A missing `-o` flag made every synthesis job fail immediately. Archived as
placeholders; do not use, and do not read them as a gap in the campaign.

`gf22_lhs_3l` excludes `gf22_lhs_3l_p1`'s designs (`--exclude`), so the two passes are disjoint.
43,602 archived designs excluding the ghost runs.

## Group 6 — 45 nm LHS and sz128

Was: `submit_45nm_nlayer_lhs.sh` and `submit_45nm_sz128.sh` over `common/nlayer_lhs_group.sh`.
Archive root: `nangate45/`. Candidates files live in the archive and are regenerated
bit-for-bit by `slurm/sweeplib/candidates.py`, which `check_design_space.py` verifies.

| Catalog group | RF | Archived run directory | Designs | Status |
|---|---|---|---|---|
| `45nm_lhs_4l`  | 1, 4, 8, 16 | `run_20260610_195135_d3223479`, `run_20260610_230312_51efc7a8`, `run_20260611_004823_793a0a9d`, `run_20260611_022851_1b2d2486` | 2,493 each | ✅ |
| `45nm_lhs_4l` (ext7) | 1, 4, 8, 16 | `run_20261119_195942_be324806`, `run_20261119_202505_a8d00cb8`, `run_20261119_203801_5a5ca93e`, `run_20261119_204754_d66e885f` | 7 each | ✅ |
| `45nm_lhs_5l`  | 1, 4, 8, 16 | `run_20260611_091354_a43fd6c4`, `run_20260611_120449_634ccce7`, `run_20260611_150955_a7b0be9c`, `run_20260611_165836_886ba4df` | 2,500 each | ✅ |
| `45nm_lhs_6l`  | 1, 4, 8, 16 | `run_20260611_183754_5be00351`, `run_20260611_215941_933c8ab7`, `run_20260612_002203_5d295619`, `run_20260612_021635_0b97189a` | 2,500 each | ✅ |
| `45nm_lhs_8l`  | 1, 4, 8, 16 | `run_20260612_041700_3d431c10`, `run_20260612_080446_c678f428`, `run_20260612_104716_eb826f3b`, `run_20260612_131637_5e7e8f6b` | 2,500 each | ✅ |
| `45nm_lhs_10l` | 1, 4, 8, 16 | `run_20260612_152852_5ce4bb6a`, `run_20260612_195601_52cde2af`, `run_20260612_230006_95a20673`, `run_20260613_014135_ad88307e` | 2,500 each | ✅ |
| `45nm_sz128_1l`| 1  | `run_20260613_061021_39f7b127` | 198 | ✅ |
| `45nm_sz128_1l`| 4  | `run_20260613_092915_0a250799` | 198 | ✅ |
| `45nm_sz128_1l`| 8  | `run_20260613_101537_70605348` | 198 | ✅ |
| `45nm_sz128_1l`| 16 | `run_20260613_103730_fd31d345` | 198 | ✅ |
| `45nm_sz128_2l`| 1  | `run_20260613_110449_079328c7` | 4,914 | ✅ |
| `45nm_sz128_2l`| 4  | `run_20260614_174103_d02199b7` | 4,914 | ✅ |
| `45nm_sz128_2l`| 8  | `run_20260615_014236_9a742bcf` | 4,914 | ✅ |
| `45nm_sz128_2l`| 16 | `run_20260615_060740_63216104` | 4,914 | ✅ |

The 4-layer candidates file holds 2,493 designs, not 2,500: the seed=42 draw of 2,500
samples snapped to 7 duplicates, which were dropped and the stems renumbered (`dense_4l_0`
to `dense_4l_2492`, no gaps). No design failed synthesis; the catalog row's note "7 hard
synthesis failures" is wrong but stays, as catalog rows are never edited.

On 2026-11-19 the group was extended to 2,500 per RF (10,000 designs): seven new designs,
`dense_4l_2493` to `dense_4l_2499`, from a fresh Latin-hypercube draw (seed 2026) over the
same space, none duplicating the 2,493. They live in
`nangate45/nangate45_lhs_4layer_ext7.txt` and were run with the group's row and that list:

    sbatch --account=amsc011 --qos=express_amsc --time=06:00:00 --mem=16G \
        slurm/sweep.sh 45nm_lhs_4l --time 02:00:00 --candidates <ext7 file>

Catapult 2026.1_1 with product Ultra (the June runs used Genesis). All 28 designs are good;
the four runs are linked into `mlp-4layer/`.

The four `45nm_sz128_2l` runs were missing from the shared archive's `README.md` until
2026-09-02, when they were found by diffing the archive's run directories against it and added.
Its RF=1 row read "incomplete — 3,444 of 4,914 missing" until a hand edit on 2026-11-17.
`make archive-index` lists runs the README does not mention.

**`45nm_sz128_2l` RF=1 was completed on 2026-11-05 without new synthesis.** The archive
held 1,470 of 4,914 designs, and 1,650 scratch reports had no QoR. Designs with input=128
and a 128-neuron layer exceed the 6 h `express_amsc` limit, and each `--resume-failed`
retry wrote a new `Catapult_N/` project folder that the report parser did not read. So
1,649 designs had finished on a retry but still looked failed. After the parser fix in
`catapult_report.py`, their reports and tarballs were rewritten from the build folders and
the run was archived: 4,913 good, 1 hard failure (`dense_2l_sz128_541`, no good attempt;
recovered on 2026-11-18, see below).
The 27 archive reports this replaced are kept in `reports_stale_20261105/` next to
`reports/`, and the scratch run keeps its old files in `data/reports/raw_stale_20261105/`
and `tarballs_stale_20261105/`, plus a per-design log, `recovered_from_retries_20261105.tsv`.

**14 sz128 designs without QoR were resynthesized on 2026-11-17/18**, so every
`45nm_sz128_*` run is now fully good: `dense_2l_sz128_541` (RF=1), nine designs of RF=4
(`dense_2l_sz128_4895`, `4904`, `4906`, `4908` to `4913`) and four of `45nm_sz128_1l`
RF=1 (`dense_1l_sz128_182`, `185`, `188`, `191`). ⚠️ They ran as **Catapult Ultra**
(`-product ultra`, 2026.1_1, license `fasic-135413`) because the Genesis licenses had
expired; every other design in the archive ran as Genesis. A full synthesis of
`dense_2l_sz128_2970` under both gave the same area (195,491 vs 195,490). The scratch
folders of the RF=4 and `1l` runs had been purged, so `make rebuild-archived` recreated
them from the archive first; jobs ran with `make rerun-failed` on `express_amsc`. The
14 archive reports and tarballs they replaced are in `reports_stale_20261118/` and
`tarballs_stale_20261118/` of each run.

`N_LAYERS=3` was supported by the old script but never run; there is no 3-layer sz128 data.

## Group 8 — Catapult Ultra sweeps

Run by `make sweep` after the Genesis licenses expired: `-product ultra`, Catapult
2026.1_1, license `fasic-135413` (5 seats). Archive root: `nangate45/`.

| Catalog group | RF | Archived run directory | Designs | Status |
|---|---|---|---|---|
| `demo_1l_20` | 1 | `run_20261119_083102_e5f26068` | 20 | ✅ |
| `demo_2l_24` | 1 | `run_20261119_110151_94639680` | 24 | ✅ |

`demo_1l_20` is a 20-design demo of the sweep path (2026-11-19): 1 node x 5 slots
on `express_amsc`, 4-5 min per design, 1.6 GB peak, no retries.
`demo_2l_24` (2026-11-19) is its two-layer counterpart, and the first sweep watched
with `make sweep-watch`: same settings, 2.7-15.8 min per design (p50 8.0), 1.6 GB
peak, no retries, 46 min of synthesis.

## Group 7 — kept, not archived

🔧 **BramFactor smoke tests** — `slurm/legacy/run_bram_test_{small,medium,large,xl,xxl}.sh`
over `common/bram_test.sh`, with their five `config_bram_test_*.json`. Output goes to
`$SCRATCH/catapult_runs_bramtest/` and is never archived. Re-run whenever a `catapult_flow`
change needs a BramFactor sanity check.

🔧 **Pipeline smoke tests** — in `slurm/legacy/`: `run_single.sh`, `run_pilot.sh`,
`run_scale.sh`, `run_scale_toy.sh`, and `run_dense_1to3layers.sh`. These use the legacy random-sampling
generator schema, which the catalog does not model, so they keep their own configs.

⚠️ `run_dense_1to3layers.sh` did produce one archived legacy run,
`run_20260506_074423_a88bd7d9` (1 design). It is part of the 1,101 legacy fixed-weight designs
excluded from training, along with `run_20260504_205339_a5d590d6` (1,000; 999 with valid
QoR, which `make provenance-diff` reports) and
`run_20260505_145920_de8c3504` (100), whose generating invocations are not recorded.

🔧 **Tools** — `archive_run.sh` (removed 2026-11-18), `check_failures.sh` (folded into
`make check-run DETAILS=1`, 2026-11-18),
`clean_runs.sh` (removed 2026-11-18),
`populate_failed_designs.py` (removed 2026-11-18), `sample_lhs_from_archive.py`,
`run_rerun_from_archive.sh` (removed 2026-11-18; see `slurm/repairs/README.md`).
