---
title: Family Involvement in Middle Management and Its Impact on the Labor Productivity of Family Firms
created: 2026-05-08T07:11:01.360984+00:00
updated: 2026-05-08T07:11:01.360984+00:00
type: papers
tags:
  - family-firm
  - labor
  - productivity
  - management
  - governance
  - China
  - survey
sources:
  - zotero:33HFK2AF
confidence: medium
---

# Family Involvement in Middle Management and Its Impact on the Labor Productivity of Family Firms

# Family Involvement in Middle Management and Its Impact on the Labor Productivity of Family Firms

## 1. Core Elements

| Element | Content |
|---|---|
| **Research Question** | Does family involvement in middle management (i.e., appointing family members to middle-level managerial positions) affect the labor productivity of family firms, and under what conditions? |
| **Core Finding** | Family involvement in middle management, measured as the percentage of familial middle managers, is negatively associated with labor productivity. This negative effect is conditional: it is significant only when the CEO is a family member (not a professional manager), when the firm is large, or when the firm is located in regions with low labor mobility. |
| **Marginal Contribution** | Shifts the focus of family involvement research from the upper echelons (ownership, board, top management) to middle management, which has more direct operational influence on workforce efficiency. Integrates organizational justice theory with agency theory to explain the mechanism, and introduces multilevel boundary conditions (individual, organizational, regional). |

## 2. Economic Story

> **Motivation:** The family business literature has overwhelmingly examined family involvement at the top of the organization—ownership stakes, board seats, and CEO/founder roles—while largely ignoring the composition of middle-management teams. Yet middle managers are the organizational layer most directly responsible for internal operations, employee supervision, and translating strategy into action, making their composition a potentially important determinant of workforce efficiency.
>
> **Hypothesis:** Drawing on agency theory and the organizational justice perspective, the authors propose that a higher proportion of family members among middle managers creates distinctive agency problems (e.g., shirking enabled by altruism, reduced accountability) and undermines perceptions of procedural and distributive justice among nonfamily employees, thereby depressing labor productivity. They further hypothesize that this negative effect is moderated by contextual factors: it should be stronger when the CEO is also a family member (weakening external oversight), in larger firms (where monitoring is harder), and in regions with low labor mobility (where nonfamily employees have fewer outside options and thus less bargaining power).
>
> **Finding:** Using a sample of 1,284 Chinese privately owned family firms, the authors find that the share of family members in middle management is negatively associated with labor productivity. Crucially, this negative relationship is not universal—it emerges only under the three hypothesized boundary conditions: familial CEO, large firm size, and low regional labor mobility. When the CEO is a professional manager, the firm is small, or labor mobility is high, the association is not statistically significant.

## 3. Preliminary Assessment

This paper may be useful for researchers studying family firm governance beyond the top-management level, a relatively underexplored area. The theoretical integration of agency theory with organizational justice offers a plausible micro-level mechanism (nonfamily employee demotivation) that could be tested more rigorously in future work. However, the research design is cross-sectional and correlational, relying on OLS regression with controls, which limits the ability to make causal claims. The data source—a large-scale survey of Chinese private enterprises—is well-suited to the research question given the prevalence of family firms in China, but the self-reported nature of key variables (e.g., proportion of family middle managers, revenue per employee) introduces potential measurement concerns. The finding that the effect is conditional on multiple moderators is interesting and suggests the relationship is context-dependent rather than universal, which may limit generalizability but enriches theoretical nuance. The paper provides a useful descriptive template for studying middle-management composition in family firms but should not be interpreted as establishing causation.

## 4. Empirical Design

### 4.1 Data and Variables

| Aspect | Detail |
|---|---|
| **Data Source** | Chinese Private Enterprise Survey (CPES), a nationally representative survey of privately owned firms in China conducted by the United Front Work Department, the All-China Federation of Industry and Commerce, the State Administration for Industry and Commerce, and the Chinese Academy of Social Sciences. The paper uses a cross-sectional sample (specific wave year not fully specified in the extracted text, but consistent with a mid-2010s wave). |
| **Y Variable** | Labor productivity: revenue per employee (total firm revenue divided by number of employees), logged in regressions. |
| **X Variable** | Family involvement in middle management: percentage of middle-level managers who are family members of the owner (continuous, 0–100%). |
| **Key Controls** | Firm age, firm size (number of employees or log revenue), industry dummies, CEO education, CEO tenure, ownership concentration, and regional economic development indicators. |
| **Sample Construction** | 1,284 privately owned family firms from the CPES. Family firms identified based on owner/family holding a controlling stake. Firms with missing data on key variables excluded. Specific trimming or winsorization procedures not detailed in the extracted text. |

### 4.2 Identification Strategy

- **Model specification:** Cross-sectional OLS regression with industry and regional fixed effects. The baseline model takes the form:

$$\ln(\text{Productivity}_{i}) = \alpha + \beta \cdot \text{FamilyMM}_{i} + \gamma \mathbf{X}_{i} + \delta_j + \epsilon_{i}$$

where $\text{FamilyMM}_i$ is the percentage of family middle managers, $\mathbf{X}_i$ is a vector of firm-level controls, and $\delta_j$ captures industry/region fixed effects. Moderation analyses add interaction terms between $\text{FamilyMM}_i$ and the three moderators (familial CEO, firm size, labor mobility).

- **Identifying assumption:** The authors do not claim a causal identification strategy. The implicit assumption for a causal interpretation would be that, conditional on the included controls and fixed effects, the proportion of family middle managers is uncorrelated with unobserved firm-level factors that independently affect labor productivity. This is a strong and untestable assumption given the cross-sectional design and potential for reverse causality (e.g., low-productivity firms may be more likely to appoint family members).

- **How is the assumption supported?** The authors include a range of firm-level controls and industry/region fixed effects to reduce omitted variable bias. They do not present an instrumental variable, difference-in-differences design, or other quasi-experimental strategy. The analysis is best interpreted as correlational.

- **Key coefficient of interest:** $\beta$, the coefficient on family involvement in middle management. The authors hypothesize $\beta < 0$, and the estimated coefficient is negative and statistically significant in the baseline specification.

### 4.3 Robustness Checks

- Alternative measure of labor productivity: revenue per employee replaced with value-added per employee (where available).
- Subsample analysis by CEO type (family CEO vs. professional CEO) to test moderation.
- Subsample analysis by firm size (large vs. small) to test moderation.
- Subsample analysis by regional labor mobility (high vs. low) to test moderation.
- Inclusion of additional control variables (e.g., ownership concentration, CEO education, firm age) to check sensitivity of the main coefficient.
- Multilevel modeling to account for the nested structure of individuals within firms within regions.

### 4.4 Mechanism and Heterogeneity

- **Mechanism:** The paper proposes two theoretical mechanisms but does not directly test them empirically. (1) Agency problems: family middle managers may shirk or free-ride due to altruism and reduced accountability. (2) Organizational justice: nonfamily employees perceive unfairness in promotion and reward decisions when family members occupy middle-management roles, reducing their motivation and productivity. Neither mechanism is measured with a direct mediator variable (e.g., employee survey data on justice perceptions or effort). The mechanism discussion remains theoretical rather than empirically validated.

- **Heterogeneity:** The paper examines three moderators that constitute the core heterogeneity analysis:
  - **Familial CEO (individual level):** The negative effect of family middle managers on productivity is significant only when the CEO is a family member; it is insignificant when the CEO is a professional (nonfamily) manager. Interpretation: a professional CEO may impose stronger performance-based accountability that counteracts nepotism at the middle-management level.
  - **Firm size (organizational level):** The negative effect is significant in large firms but not in small firms. Interpretation: in small firms, the owner can directly monitor all employees, reducing the agency costs of family middle managers; in large firms, monitoring is harder and the costs of nepotism are amplified.
  - **Regional labor mobility (regional level):** The negative effect is significant in regions with low labor mobility but not in high-mobility regions. Interpretation: when labor markets are tight and mobility is high, nonfamily employees can exit, disciplining the firm; when mobility is low, employees are trapped and the demotivating effects of perceived injustice are more pronounced.
