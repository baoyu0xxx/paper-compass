You are continuing to analyze an academic paper. You have already produced the Overall Understanding section (Core Elements, Intellectual Narrative, Preliminary Assessment). Now add the following EMPIRICAL DESIGN section.

This section must follow the same cautious, factual academic tone. Describe what the paper actually did — do not evaluate whether it was "well done" unless the authors themselves discuss limitations.

## 4. Empirical Design

### 4.1 Data and Variables

Answer the following concisely:

- **Data source:** What dataset(s) does the paper use? Include time period and geographic coverage. Note whether the data is primary (collected by authors) or secondary.
- **Outcome variable:** What is being explained or predicted? How is it measured?
- **Key explanatory variable:** What is the main independent variable or treatment? How is it measured or manipulated?
- **Key controls/covariates:** List 3-5 most important control variables or additional predictors.
- **Sample construction:** How was the final estimation sample derived? (e.g., inclusion/exclusion criteria, data cleaning steps, handling of missing values)

Format this as a compact table where appropriate:

| Aspect | Detail |
|---|---|
| Data Source | ... |
| Outcome Variable | ... |
| Key Explanatory Variable | ... |

### 4.2 Design and Methods

Describe the research design and analytical approach:

- **Design type:** What is the overall research design? (e.g., randomized experiment, difference-in-differences, instrumental variables, regression discontinuity, panel data analysis, cross-sectional regression, structural equation modeling, qualitative comparative analysis)
- **Model/approach:** What is the primary analytical method? Describe conceptually (e.g., "linear regression with fixed effects", "two-stage least squares", "thematic analysis of interview transcripts")
- **Key assumptions:** What must hold for the findings to be valid? (e.g., parallel trends, exclusion restriction, unconfoundedness, saturation in qualitative data)
- **How assumptions are supported:** What evidence or arguments do the authors provide? (e.g., balance tables, pre-trends plots, placebo tests, member checking, triangulation)

Write as concise prose. Use mathematical notation ($Y$, $\beta$, etc.) only if the paper does so centrally.

### 4.3 Robustness and Sensitivity

List the robustness checks, sensitivity analyses, or validation procedures the authors performed:

- [Brief description of each check, e.g., "Alternative outcome measure: using X instead of Y"]
- [e.g., "Subsample analysis: excluding observations with characteristic Z"]
- [e.g., "Placebo/falsification test: ..."]
- [e.g., "Alternative model specification: ..."]

Use `- ` bullet format. Do not describe results in detail unless a check overturns the main finding.

### 4.4 Mechanism and Heterogeneity

If the paper explores WHY the effect or phenomenon occurs (mechanism/process) or for WHOM/under WHAT conditions it varies (heterogeneity/moderation):

- **Mechanism/Process:** What causal channel or process does the paper propose and test? How is the mediating variable measured or identified?
- **Heterogeneity/Moderation:** Across what dimensions does the finding vary? (e.g., subgroups, contexts, conditions)

If the paper does NOT explore mechanisms or heterogeneity, state: "The paper does not explore causal mechanisms." or "The paper does not examine heterogeneous effects."

## Output

Append this section to your previous wiki page DIRECTLY below the existing sections. Do NOT wrap the output in code fences. The combined output should start with `---` (frontmatter), then:

- `# Paper Title`
- `## 1. Core Elements` (table)
- `## 2. Intellectual Narrative` (prose)
- `## 3. Preliminary Assessment` (prose)
- `## 4. Empirical Design` (subsections as above)

All in one continuous markdown document with a single frontmatter block at the very top.
