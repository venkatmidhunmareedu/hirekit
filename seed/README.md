# Seed data

Synthetic data for the demo and for the two evals (US-02-005 agreement, US-02-006 name-swap). Loaded and validated by `backend/app/seed/data.py`. Everything here is invented: no real people, no real employers or schools, emails only on `example.com`, phone numbers in the fictional 555-01xx range. Cities are real, large and generic, and are never tied to a street address, employer or school.

## Layout

- `roles/<slug>.md`: role title, job description, and criteria. Each criterion has `kind` (must_have or nice_to_have), `weight`, and five rubric descriptors for levels 0 to 4 (0 means no evidence).
- `resumes/<id>.txt`: the source text of a resume. `<id>.pdf` or `<id>.docx` sits next to it, built from the text by `backend/scripts/build_seed_resumes.py` and committed (ADR-0012). The builder picks the file type and the layout from a hash of the id.
- `labels.csv`: `resume_id,criterion,label,rationale`, one row per resume and criterion of its role, label 0 to 4.
- `pairs.csv`: `base_id,swap_id,origin_pair,signals_swapped`, one row per name-swap pair.

## Ids and pairs

A resume id is `<role slug>-<number>`. For each base resume `backend-NN` the swap copy is `backend-NN<suffix>`; the suffix is chosen so the builder gives the copy the same file type and layout as its base. A swap copy repeats the base text exactly, except the name-linked signals: name, email, profile handle, pronouns where the base states them, nickname and city. The copy repeats the base labels exactly. `origin_pair` reads `<base origin>:<swap origin>`, and the genders differ in every pair.

## What the data can and cannot show

- The resumes, the labels and (later) the scores all come from the same model family. The agreement eval is therefore a consistency check, not a comparison with independent ground truth.
- Anonymization is a floor, not proof of fairness. It removes named signals; proxy signals such as schools, clubs, gendered wording and career gaps can remain. A passing name-swap eval says the named signals did not move the scores on these pairs, nothing more.
