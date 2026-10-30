# Supplier price list comparator

[Português](README.md) · **English** · [Español](README.es.md)

[![tests](https://github.com/rodrigoteixeiraferreira/comparador-listas-fornecedores/actions/workflows/ci.yml/badge.svg)](https://github.com/rodrigoteixeiraferreira/comparador-listas-fornecedores/actions/workflows/ci.yml)

![Supplier price list comparator: zero false positives as the acceptance criterion](docs/img/capa_repositorio.png)

A system that reads supplier price lists (spreadsheet, PDF and photo), matches every line to a supermarket's
catalog and tells, product by product, who sells cheapest. There was a single acceptance criterion:
**zero automatically confirmed matches where brand, size or unit disagree.**

This repository has two parts:

- **the case study** of the system I delivered to a supermarket in Argentina in October 2026: the
  problem, the decisions and the numbers. That project's code and data belong to the client and are not here;
- **a demo rewritten from scratch** with fictional data, which runs and proves itself: the same design, an invented
  world and an answer key to check every decision.

The demo's brands, suppliers, prices and barcodes are invented. The screens of the original shown here are replicas
with fictional data. The demo panel screens below are in English; the other images and the detailed docs are in Portuguese, and the
original product was in Spanish.

## The problem

A supermarket receives dozens of price lists a month, each supplier with its own format and
abbreviations. The buyer had built a comparator with an AI assistant. That system's backup showed two numbers:

- out of 5,129 products, only 199 (3.9%) had prices from two or more suppliers;
- out of the 475 pairs the system confirmed on its own, **63 (13.3%) had the wrong size**.

There was a single cause: the system compared word similarity, and size was just text. A 1 kg pack matched the 2 kg
pack with a perfect score, because the whole name matched.

## The thesis

1. **Size, unit and brand are conditions, not points.** If they disagree, the pair is not even a candidate.
2. **Text similarity never confirms.** It only ranks candidates for human review.
3. **AI interprets and ranks; the database computes.** No price, quantity or difference comes out of a model: every
   number is a SQL query, traceable to the list and date it came from.
4. **A growing review queue is not a defect; a false positive is.**

## Architecture

```mermaid
flowchart TD
    L["Supplier list<br/>spreadsheet, PDF or photo"] --> F{"Known format?"}
    F -- yes --> A["Reader<br/>code"]
    F -- "photo" --> I["Two independent AI readings<br/>only what both read alike goes on"]
    A --> P{"Gate<br/>7 checks"}
    I --> P
    P -- "failed" --> ANT["The previous list stays valid"]
    P -- passed --> E["Attribute extractor<br/>brand, type, variety, size, unit"]
    E --> C["SQL cascade<br/>barcode, supplier code,<br/>confirmed equivalence, attributes"]
    C --> N["Pair with confidence level and reason"]
    N --> W["Price comparison"]
    N -- "only the doubtful" --> H["Human review"]
    H -- "records «it is», «it is not» and «the store doesn't carry it»" --> AP["Learning"]
    AP --> C
    N --> AU["Sample audit"]
    AU -- "error above 2%" --> D["That decision type<br/>stops deciding on its own"]
```

| Layer | Technology |
|---|---|
| Database, rules and computation | Postgres on Supabase: versioned migrations, functions, views, RLS |
| List reading and extraction | Python (openpyxl, pdfplumber) |
| Photo reading | double reading by two different Claude models, with the answers recorded |
| Tests | pytest; on GitHub Actions, against the local Supabase in Docker |
| Panel | Next.js 16, React 19, Tailwind 4; Supabase login; Portuguese, Spanish and English |
| Development | Claude Code with the Supabase MCP |

## The demo

A seed generates a whole world: the market (251 products from 16 invented brands), the store catalog (158 products),
the September and October lists of two suppliers (Mayorista Norte as a spreadsheet, prices without VAT; Distribuidora
Andina as a PDF, with VAT and abbreviations) and the photo of a printed list from a third one (Mercantil Ombú). The
generator plants traps in random places and writes the **answer key** for every line: which product it really is,
or none. The system never reads the answer key; only the tests do.

The traps: 1 kg × 2 kg, swapped brand, swapped variety, 6-pack × single unit, the extra word that makes it another
product («SIN TACC», gluten-free), the abbreviation the vocabulary doesn't know, the closed-box price, the barcode of
another size, the supplier code reused for another product, and the price typed with an extra zero.

| What the demo proves | Result |
|---|---|
| Wrong confirmed pairs, checked against the answer key | **0**, in 5 worlds (21 lists) |
| Deliberately corrupted lists the gate holds at the right check | **51 of 51** |
| Good lists the gate holds | 0 of 20 |
| Questions to the reviewer the next month, after they answered the previous month's | less than half |
| The photo read by two models (Sonnet and Haiku) | 44 of 44 lines identical in both readings, and right |

The sample audit of seed 1 (the demo's auditor answers from the answer key):

| Decision type | Sample | Errors | True error, 95% confidence | Decision |
|---|---|---|---|---|
| barcode | 50 | 0 | up to 5.8% | stays on |
| supplier code | 50 | 0 | up to 5.8% | stays on |
| identical attributes | 40 | 0 | up to 7.2% | stays on |
| high similarity (on trial) | 18 | 18 | — | **switched off** |
| identity with doubtful price (on trial) | 1 | 0 | up to 95% | stays on trial: a small sample decides nothing |

### The panel

Three screens, in Portuguese, Spanish and English, reading the demo database behind a login: database status, price
comparison and review queue. What the system decides shows in the reader's language; the supplier's line stays as it
came, tagged «original». The three review buttons really record. The panel isn't online: it runs on localhost, and
the live demo is on request.

![The review queue: «it is not», «the store doesn't carry it» and «it is this one»; at the end, the comparison with the pair the person decided](docs/img/en/revisao.gif)

In the GIF, the person says «it is not» to a line's first candidate and then «the store doesn't carry it»: the queue
drops from 25 to 24. On the flour whose price was typed with an extra zero, the attributes are identical and they say
«it is this one». In the comparison, the flour shows as identified by the person, but out of the competition until
someone checks the price.

<p>
<a href="docs/img/en/tela_estado.png"><img src="docs/img/en/tela_estado.png" width="270" alt="Database status"></a>
<a href="docs/img/en/tela_comparacao.png"><img src="docs/img/en/tela_comparacao.png" width="270" alt="Price comparison"></a>
<a href="docs/img/en/tela_revisao.png"><img src="docs/img/en/tela_revisao.png" width="270" alt="Review queue"></a>
</p>

### How to run

```bash
python -m venv .venv && . .venv/bin/activate     # on Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pricelists.world --seed 1              # the seed-1 world, in generated/seed-1
pytest                                           # without a database, the database tests are skipped

supabase db start                                # local Postgres with the migrations (needs Docker)
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
pytest                                           # now with the proof in the database
python -m pricelists.pipeline --seed 1           # loads, reviews, audits and shows each list's numbers

cd web && npm install
cp .env.example .env.local                       # the Supabase URL and public key (supabase status)
npm run dev                                      # the panel at http://localhost:3000, with a Supabase user
```

### What is where

| Where | What |
|---|---|
| `src/pricelists/world/` | the generator of the fictional world, the lists, the photo and the corruptions |
| `src/pricelists/extract.py` | the attribute extractor: what it doesn't recognize stays as a «leftover word», never guessed |
| `src/pricelists/readers.py`, `ai_reader.py` | the spreadsheet and PDF readers; the photo's double reading |
| `src/pricelists/gate.py` | the 7-check gate |
| `supabase/migrations/` | the schema, the SQL cascade, the views, RLS and the three review buttons |
| `src/pricelists/audit.py` | the sample audit |
| `prompts/`, `data/recorded/` | the photo-reading prompt and the two recorded readings |
| `tests/` | the proof: generator, extractor, readers, gate, cascade, audit and the panel in the database |
| `web/` | the panel: the three screens, the three languages and the script for the screenshots and the GIF |

### The limits

- **The world and the rules have the same author.** Traps come from seeds, some writings are deliberately unknown to
  the vocabulary, and the proof runs on several worlds; still, a generated world behaves better than real lists. The
  original project was proven on the real lists; this demo proves the mechanism.
- **The gate's limits** (price change, price against cost, continuity) are calibrated for this world.
- **The photo was read once** by two Claude Code subagents, each with only the photo and the prompt, and the readings
  were recorded: the demo does not call the API. On this clean photo both readings agreed on everything; the
  disagreement queue is proven by a test that plants divergence.
- **The demo's reviewer and auditor are simulated:** they answer from the answer key. In the original, a person did.
- **The panel runs on localhost**, with the Supabase login. Through the API, only the three review buttons write, via
  database functions that require a login; the tables accept no writes from panel users.

## The decisions that mattered most

- **The leftover word.** Without a barcode, every word that appears on one side only must be noise declared in the
  vocabulary, or the pair doesn't confirm. In the original, this rule took down 365 pairs that looked right.
- **A negative decision is data.** The reviewer's «it is not this one» applies at every step, including the barcode,
  and a rejected offer never comes back. «The store doesn't carry it» is a decision too: the line doesn't return to
  review.
- **Every pair has a level and a reason:** 1 human decision, 2 barcode, 3 strong rule, 4 under review. Only levels 1
  to 3 count as confirmed; a pair under review never silently wins the comparison.
- **Identity and price are two questions.** A price far from cost doesn't undo the identification: the product stays
  identified and that line just doesn't compete until someone checks the price.
- **The new list waits at the gate.** Seven checks before it replaces the previous one. Until it passes, the previous
  one stays valid.
- **The machine has a measured error rate.** By random sample, per decision type, with a 2% limit.

The original's details are in [`docs/`](docs/), in Portuguese.

## Results of the original project

In less than four weeks, from the database to the panel. Delivered on 17 Oct 2026; coverage figures are from the database on 30 Oct 2026.

| Measure | Value |
|---|---|
| Confirmed pairs with incompatible brand, size or unit | **0**, in every checking round |
| Store products with an identified supplier | 4,026 of 4,929 (81.7%) |
| Products with prices from two or more suppliers | 2,569 (52%); in the previous system, 199 (3.9%) |
| Suppliers whose lists were read | 74, from spreadsheets, PDFs and photos |
| AI error on confirmed pairs, by sample | 1 in 145 (0.7%); with 95% confidence, at most 3% |
| Unknown supplier (blind test) | 0 wrong pairs; 0 to 4 items per 100 lines on the buyer's desk |
| Screen load time | from 10–19 s (or an error) to under 2 s |

### Screens of the original

Faithful replicas of the panel's design, with fictional data. The product was in Spanish.

![Replica of the database status](docs/img/tela_estado_replica.png)

![Replica of the price comparison](docs/img/tela_comparacao_replica.png)

## How I worked

- **One document of current rules**, read in full before any proposal. A decision made with real data isn't
  reopened unless asked.
- **Every session opens with a brief and closes with a report**, a version index and cleanup of superseded files.
- **A test suite at the end of every session.** Tests never write to the real database.
- **Migrations proven on a copy** before the real database; an applied migration is never edited.
- **AI cost measured**, with a monthly cap.

## Contact

Rodrigo Teixeira Ferreira — automation, data and AI agents. Open to contracts and full-time roles.
[LinkedIn](https://www.linkedin.com/in/rodrigo-teixeira-ferreira-2b00a31b6/) · [flechamedicina@gmail.com](mailto:flechamedicina@gmail.com) · [GitHub](https://github.com/rodrigoteixeiraferreira)
