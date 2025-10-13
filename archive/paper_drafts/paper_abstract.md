Objective: We evaluated GPT-5 on PubMed-derived clinical yes/no/no-evidence questions and assessed factors associated with task difficulty, including discipline, citation volume, publication year, and the availability and provenance of contextual abstracts.

Data and design: The primary evaluation set contained 8,530 items (8,366 unique questions) with three-way labels (Yes/No/No Evidence). We computed exact-match answer accuracy overall, by field, and across citation- and year-binned strata. A logistic regression modeled correctness as a function of log(1+citations), publication year, field (top categories), question length, and ground-truth evidence quality. We additionally tested four context conditions on a 500-item subset of the originally incorrect questions: (i) no additional context, (ii) the correct abstract for the source DOI, (iii) a random abstract from a different DOI, and (iv) PubMed top-3 abstracts retrieved by relevance while excluding the same DOI.

Results: GPT-5 achieved overall accuracy 0.678 (status 200 for all items). Performance varied by domain, with higher accuracy in Tobacco, Drugs and Alcohol (0.746; n=169), Lungs and Airways (0.723; n=382), Pain and Anaesthesia (0.721; n=337), Infectious Disease (0.701; n=405), and Cancer (0.696; n=621), and lower accuracy in Complementary and Alternative Medicine (0.576; n=92) and Health and Safety at Work (0.521; n=48). Accuracy increased monotonically with citation count (e.g., 0.591 for [0–5), 0.617 for [5–12), 0.666 for [12–21), 0.721 for [21–39), and 0.791 for [39–1035)). Logistic regression indicated that citation volume is a significant predictor of correctness: per one-unit increase in log(1+citations), the odds of a correct answer increased by 34% (OR=1.34; 95% CI: 1.29–1.40). Binned year analysis showed a mild upward trend for more recent publications.

Context experiments (subset): On the 500-item subset originally answered incorrectly, accuracy was 0.164 with no additional context, 0.790 with the correct abstract, 0.116 with a random abstract, and 0.150 with PubMed top-3 abstracts (n=20 for PubMed in the current run). Explicit accuracies by condition:

- None (no added context): 0.164 (n=500)
- Correct abstract: 0.790 (n=500)
- Random abstract: 0.116 (n=500)
- PubMed top‑3 abstracts (excluding same DOI): 0.150 (n=20)

These results suggest large gains from providing the correct source abstract and modest to negative effects from unrelated or loosely relevant abstracts.

Conclusion: GPT-5 performs strongly on clinical yes/no/no-evidence judgments, with notable variation by domain and a robust association between higher citation volume and accuracy. Providing the correct abstract substantially improves performance on previously incorrect items, underscoring the importance of high-precision retrieval for evidence-based clinical QA.


