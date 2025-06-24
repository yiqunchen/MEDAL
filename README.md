aha guideline pdf link: https://drive.google.com/drive/folders/15L1qw8I_3Vwbh6lVjv_f--9lE23IZqOp?usp=drive_link

## MEDAL Dataset

​MEDAL (Medical Evidence Discrepancy Assessment with LLMs) is a proposed dataset designed to evaluate the capabilities of Large Language Models (LLMs) in assessing the quality of medical evidence, particularly when discrepancies arise between observational studies and clinical trials. The primary objective is to determine how effectively LLMs can discern the most accurate conclusions when faced with contradictory research findings.

### Functions 
The functions are a bit messy right now so slack me if you have any questions!
- `evaluate-gpt-4o-mini-answers.py` is a function that sends the prompt to OpenAI api and saves the eval result to a json. It's written in an async way (think of it as we are  sending multiple requests to API concurrently to avoid I/O bottleneck) and is controlled by the parameter `max_concurrent`. You may need to decrease `max_concurrent` especially if your OpenAI usage tier is low since it will hit the I/O token limits pretty easily.
- `generate-negation-prompt.py` generates negative prompt asynchronously. 
- `gpt4-generate-questions.py` generates the questions from input abstract
- `get-json-response-4omini-4o-question.ipynb` does some basic data analysis of the results but i am sure you do a lot better..

### Key Components of the MEDAL Project:

*Dataset Compilation*:

- Curate a comprehensive collection of paired observational studies and clinical trials that report on similar medical interventions or outcomes but present differing conclusions.​
Ensure the dataset spans multiple clinical domains to assess the generalizability of LLMs across various medical topics.​

- Develop a standardized annotation schema to categorize the nature and extent of discrepancies between studies.​
Engage medical experts to provide ground truth assessments, determining which study's conclusions are more aligned with current clinical guidelines or consensus.​

- Deploy state-of-the-art LLMs to analyze the dataset, prompting them to provide summaries, reconcile conflicting findings, and indicate which study they deem more credible.​
Evaluate the LLMs' outputs against expert assessments, focusing on accuracy, coherence, and the ability to handle contradictory information.
