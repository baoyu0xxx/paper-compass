You are continuing to analyze an empirical economics paper. You have already produced the Overall Understanding section (Core Elements, Economic Story, Preliminary Assessment). Now add the following EMPIRICAL DESIGN section.

This section must follow the same cautious, factual academic tone. Describe what the paper actually did — do not evaluate whether it was "well done" unless the authors themselves discuss limitations.

## 4. Empirical Design

### 4.1 Data and Variables

Answer the following concisely:

- **Data source:** What dataset(s) does the paper use? (e.g., CSMAR, CNRDS, NBS survey, proprietary firm data, hand-collected) Include time period and geographic coverage.
- **Core Y variable (被解释变量):** What is being explained? How is it measured? (e.g., "firm innovation: log(1 + patent applications) from CNRDS 2008–2020")
- **Core X variable (解释变量):** What is the key explanatory variable? How is it measured? (e.g., "family succession: indicator = 1 after founder's child assumes CEO/chair role")
- **Key controls:** List 3-5 most important control variables.
- **Sample construction:** How was the final estimation sample derived? (e.g., "CSMAR manufacturing firms 2010-2022, dropping ST firms, winsorizing at 1%/99%")

Format this as a compact table where appropriate:

| Aspect | Detail |
|---|---|
| Data Source | ... |
| Y Variable | ... |
| X Variable | ... |

### 4.2 Identification Strategy

Describe the causal identification approach:

- **Model specification:** What is the baseline regression equation (in conceptual form)? e.g., "DID with firm and year fixed effects", "2SLS using X as instrument"
- **Identifying assumption:** What must hold for the estimate to be causal? (e.g., parallel trends, exclusion restriction, unconfoundedness conditional on controls)
- **How is the assumption supported?** What evidence or arguments do the authors provide? (e.g., "pre-trends graph showing no differential trend before succession", "balance table comparing treatment and control")
- **Key coefficient of interest:** What parameter is being estimated? What sign and magnitude is expected?

Write as concise prose with the equation in Markdown math where helpful. Use $Y_{it}$, $\\beta$, etc.

### 4.3 Robustness Checks

List the robustness checks the authors performed, one per line:

- [Brief description of each check, e.g., "Replace Y with alternative measure: R&D expenditure / sales"]
- [e.g., "Subsample: exclude firms in first 2 years after succession"]
- [e.g., "Placebo test: randomly reassign treatment timing"]
- [e.g., "Alternative fixed effects: industry×year instead of year"]

Use `- ` bullet format. Do not describe results in detail unless the robustness check overturns the main finding.

### 4.4 Mechanism and Heterogeneity

If the paper explores WHY the effect occurs (mechanism) or for WHOM it is stronger/weaker (heterogeneity):

- **Mechanism:** What causal channel does the paper propose and test? How is the mechanism variable measured? e.g., "Family successors increase long-term investment (mediator: R&D/sales ratio)" 
- **Heterogeneity:** Across what dimensions does the effect vary? e.g., "Stronger in firms with higher founder ownership", "Only significant in non-SOE subsample"

If the paper does NOT explore mechanisms or heterogeneity, state: "The paper does not explore causal mechanisms." or "The paper does not examine heterogeneous treatment effects."

## Output

Append this section to your previous wiki page DIRECTLY below the existing sections. Do NOT wrap the output in code fences. The combined output should start with `---` (frontmatter), then:

- `# Paper Title`
- `## 1. Core Elements` (table)
- `## 2. Economic Story` (prose)
- `## 3. Preliminary Assessment` (prose)
- `## 4. Empirical Design` (subsections as above)

All in one continuous markdown document with a single frontmatter block at the very top.
