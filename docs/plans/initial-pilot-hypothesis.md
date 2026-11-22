# Initial segment, incentives and scale hypothesis

This is a proposed design hypothesis for BR-BUILD-003, not validated demand,
an agreed commercial offer or a live pilot authorization. It connects the
current acquisition software to the user's longer-term goal of serving two
million U.S. households, including immigrants.

## Initial segment

Start with a small acquisition or community-housing team that already helps
households understand a specific property opportunity and collect supporting
documents. The first software customer is the team reviewing cases; the
household is the beneficiary of a clearer, source-backed decision process.
This matches the existing evidence, underwriting and review code better than
immediately attempting a national direct-to-consumer financial service.

Use Dayton, Ohio as a provisional design geography for a single-market
discovery exercise. This is a planning choice, not a finding about local
demand, available partners, property prices or eligibility. A live pilot
requires a willing delivery partner, lawful source access, verified local
workflow requirements and an affordable operating model. Change the geography
if those conditions are better satisfied elsewhere.

Define the first household use case by service need: a person considering a
property needs understandable costs, a document checklist, source references
and a visible explanation of what remains unresolved. Include immigrants and
U.S.-born households in that service design. Language and accessibility needs
inform service delivery; identity is not a substitute for evidence supporting
an individual financial decision. The initial software is a review tool and
does not itself supply credit, eligibility determinations or a property.

## Incentive and payer hypotheses

| Participant | Proposed value to test | Evidence needed |
| --- | --- | --- |
| Household | Understand the complete cost assumptions, avoid repeated document requests, and see why a decision is held | Comprehension interviews, document rework count, time to a reviewed explanation, accessible-language testing |
| Acquisition or housing team | Reduce manual reconciliation and repeated analysis; inspect the exact source behind a number | Analyst minutes per case, correction rate, exception backlog, reviewed-packet turnaround |
| Document or service provider | Receive a clear request and know which version or missing item is needed | Resubmission rate, response time, completeness and consent records |
| Paying organization | Obtain a measurable workflow benefit for a predictable software/service cost | Willingness-to-pay discovery, cost per completed review, support burden and renewal interest |

The starting revenue hypothesis is an organization subscription or a
transparent per-reviewed-case service fee. No price, commission arrangement,
household charge, incentive payment or return promise is established here.
Do not describe a software calculation as a guaranteed approval, purchase,
savings amount or investment outcome.

## Discovery and release sequence

First replay a bounded set of synthetic cases with missing, contradictory,
stale, revised and correctly reviewed evidence. Record which steps require
human effort. Use the demonstrated quote change as one case, not the entire
validation population.

Before a live pilot, interview prospective reviewers and beneficiaries,
confirm the source and consent workflow, validate service responsibilities,
and agree on review and escalation rules. A proposed initial live cohort of
20 cases is an operational learning exercise; it would not establish a
calibrated probability model or justify national-scale statistical claims.

Choose release thresholds before observing the pilot results. Critical money
fields must reconcile exactly for the evaluated cases, unresolved sources
must remain visibly held, and every reviewed result must preserve its source
trace. Measure human review minutes and participant comprehension as well as
software latency. Expand only after the partner can support the observed
exceptions, accessibility needs and cost profile.

## Unit economics and resource model

Keep software customer and household counts separate. A target of two million
households does not mean two million simultaneous calculations.

Estimate workload from explicit assumptions:

`pages per second = households × monthly active fraction × documents per active household per month × pages per document ÷ seconds per month × peak factor`

For illustration only, two million households, 10% monthly activity, six
documents per active household, four pages per document and a 30-day month
imply about 1.85 pages/second averaged over the month; an assumed tenfold peak
implies about 18.5 pages/second. These are workload arithmetic, not measured
capacity, adoption forecasts or a GPU-sizing result. The real distribution,
page types, concurrency, latency target, retries and human-review fraction
must be observed.

Measure contribution per completed review as collected revenue minus
allocated infrastructure, model/provider charges if later enabled, human
review, support and source costs. Track acquisition cost per activated paying
organization and per served household separately. An efficient GPU kernel
does not by itself establish viable total delivery economics.

## Source context and decision status

The user supplied Welcoming America's
[Guide to Immigrant Economic Development](https://welcomingamerica.org/wp-content/uploads/2021/04/WA_ImmigrantEconomicDevelopment_FINAL_web.pdf).
It frames immigrant inclusion as part of local economic development. The
related [Welcoming Economies Playbook](https://welcomingamerica.org/wp-content/uploads/2021/01/Welcoming-Economies-Playbook.pdf)
includes homeownership among its economic-development areas. The segment,
geography, commercial model and validation proposal above are this project's
working hypotheses, not endorsements or findings from those publications.

The [ticket plan](document-engine-tickets.md) carries the subsequent consent,
accessibility, source integration, outcome-data, load and release gates. The
current implemented increment remains a local deterministic research
demonstration with synthetic source documents.
