---
title: A Far-Reaching Parental Love? Co-Governance of Intergenerational Succession and Innovation Activities in Chinese Family Firms
created: 2026-05-08T07:09:30.120349+00:00
updated: 2026-05-08T07:09:30.120349+00:00
type: papers
tags:
  - family-firm
  - succession
  - governance
  - innovation
  - China
sources:
  - zotero:PVQ9Y36E
confidence: medium
---

# A Far-Reaching Parental Love? Co-Governance of Intergenerational Succession and Innovation Activities in Chinese Family Firms

# A Far-Reaching Parental Love? Co-Governance of Intergenerational Succession and Innovation Activities in Chinese Family Firms

## 1. Core Elements

| Element | Content |
|---|---|
| **Research Question** | How does intergenerational co-governance — defined as both the founder and successor holding key positions in the TMT/governing body simultaneously — affect innovation activities in Chinese family firms? |
| **Core Finding** | Co-governance is positively associated with family firm innovation. However, the effect is channeled toward low-risk innovations rather than high-risk, more inventive ones. The positive relationship is moderated by intra-family characteristics: kinship type, age difference, and gender difference between founder and successor. |
| **Marginal Contribution** | Conceptualizes co-governance as a distinct transitional governance structure during succession (rather than treating succession as a single event) and empirically links it to innovation. Introduces altruism theory as an explanation for the succession–innovation nexus and examines heterogeneity along intra-family relationship dimensions largely unexplored in prior work. |

## 2. Economic Story

> **Motivation:** Intergenerational succession is a critical challenge for Chinese family firms, yet prior research has largely treated succession as a discrete event (e.g., the successor assuming the CEO role), overlooking the extended transitional period during which founder and successor jointly govern. Meanwhile, the literature on succession and innovation has produced contradictory findings — some arguing that long-term orientation fosters innovation, others that risk aversion during succession suppresses it — suggesting a need to identify the specific governance conditions under which each effect dominates.
>
> **Hypothesis:** The authors propose that co-governance, as a transitional governance structure, represents a form of parental altruism in which founders invest in the firm's future to smooth the succession path. This altruistic motivation should increase innovation. However, because altruism is also linked to risk aversion (preserving the family legacy), co-governance should steer resources toward lower-risk innovations. The strength of this effect is expected to vary with the nature of the intra-family relationship (kinship closeness, age gap, gender).
>
> **Finding:** Using a panel of listed Chinese family firms (2006–2015), the authors find evidence consistent with their hypotheses: co-governance is associated with higher innovation output, but the innovation tends to be incremental (low-risk) rather than radical (high-risk). The effect is moderated by kinship type, age difference, and gender difference between founder and successor, suggesting that intra-family relational dynamics shape the innovation consequences of succession governance.

## 3. Preliminary Assessment

This paper may be useful for researchers studying the governance dynamics of family firm succession and its real effects on firm strategy. The conceptualization of co-governance as a distinct governance regime — rather than a binary succession/no-succession indicator — offers a potentially valuable framing for empirical work on succession processes. The use of altruism theory to connect intra-family relationships to innovation outcomes provides a behavioral mechanism that is distinct from standard agency or socioemotional wealth explanations.

However, several cautions apply. The identification strategy appears to rely on standard panel regressions with fixed effects rather than a quasi-experimental design, which limits the ability to make strong causal claims about co-governance's effect on innovation. The sample is restricted to publicly listed firms, which represent a small and non-random subset of Chinese family firms, potentially limiting generalizability. The paper may be most useful as a source of hypotheses and conceptual framing rather than as a model of causal identification.

## 4. Empirical Design

### 4.1 Data and Variables

| Aspect | Detail |
|---|---|
| **Data Source** | Unbalanced panel of Chinese family firms listed on the Shanghai and Shenzhen Stock Exchanges, 2006–2015. Family firm status and co-governance indicators appear to be hand-collected from annual reports and public filings. |
| **Y Variable** | Innovation activities — likely measured using patent-based indicators (e.g., patent applications or grants), potentially distinguishing between invention patents (high-risk/inventive) and utility model/design patents (low-risk/incremental). The paper explicitly tests differentiation by innovation risk level. |
| **X Variable** | Co-governance: indicator variable = 1 when both the founder (or founding generation) and a next-generation family member simultaneously hold key positions in the firm's TMT or governing body. |
| **Key Controls** | Firm-level controls likely include firm size, age, leverage, ROA, R&D intensity, ownership concentration, and industry/region indicators. Exact list not fully specified in the available text. |
| **Sample Construction** | 4,694 firm-year observations from listed Chinese family firms over 2006–2015. Likely excludes ST/PT (special treatment) firms and firms with missing data on key variables. Standard winsorization of continuous variables is probable but not explicitly confirmed in the available text. |

### 4.2 Identification Strategy

- **Model specification:** The baseline model appears to be a panel regression with firm and year fixed effects:

$$Innovation_{it} = \alpha + \beta \cdot CoGovernance_{it} + \gamma \cdot X_{it} + \mu_i + \lambda_t + \varepsilon_{it}$$

where $\mu_i$ are firm fixed effects and $\lambda_t$ are year fixed effects. Interaction terms with moderators (kinship, age difference, gender difference) are added to test heterogeneity.

- **Identifying assumption:** Conditional on firm fixed effects and time-varying controls, the timing of co-governance initiation is not driven by unobserved factors correlated with innovation trends. In other words, the paper assumes that once firm-level heterogeneity and common time trends are absorbed, the remaining variation in co-governance is plausibly exogenous to innovation outcomes.

- **How is the assumption supported:** The available text does not describe explicit pre-trend tests, instrumental variables, or other quasi-experimental validation strategies. The authors appear to rely on the richness of control variables and fixed effects to address endogeneity concerns. This is a notable limitation, as reverse causality (innovative firms may be more likely to adopt co-governance) and omitted variable bias remain plausible threats.

- **Key coefficient of interest:** $\beta$, the coefficient on co-governance, expected to be positive and significant. The paper also examines $\beta$ for low-risk vs. high-risk innovation separately, expecting a positive effect primarily for low-risk innovation.

### 4.3 Robustness Checks

Based on the available text, the specific robustness checks are not fully enumerated. Likely checks in a study of this type include:

- Alternative measures of innovation (e.g., R&D expenditure, patent counts vs. patent citations)
- Alternative definitions of co-governance (e.g., varying the threshold for "key position")
- Exclusion of firms in the earliest/latest years of the sample
- Controlling for potential confounders such as industry-level innovation trends
- Subsample analyses by firm characteristics
- Addressing potential sample selection bias (e.g., Heckman correction or propensity score matching)

*Note: The available text does not provide a complete list of robustness checks; the above are inferences based on standard practice in this literature.*

### 4.4 Mechanism and Heterogeneity

- **Mechanism:** The paper proposes parental altruism as the theoretical mechanism linking co-governance to innovation. Founders engaging in co-governance are motivated by long-term, altruistic concerns for their children's future leadership, which encourages investment in innovation as a form of "far-sighted" strategic preparation. However, this same altruism constrains the type of innovation: founders prefer lower-risk, incremental innovations that preserve family legacy rather than high-risk, radical innovations. The mechanism is tested indirectly through the risk-differentiation of innovation outcomes (low-risk vs. high-risk patents) rather than through a formal mediation analysis.

- **Heterogeneity:** The paper examines three moderators drawn from the altruism framework:
  - **Kinship type:** The relationship between founder and successor (e.g., parent–child vs. other kinship ties) moderates the co-governance–innovation link, reflecting differences in altruistic intensity.
  - **Age difference:** The age gap between founder and successor is expected to moderate the effect, as larger gaps may alter the power dynamics and altruistic motivation within co-governance.
  - **Gender difference:** Whether the successor is male or female moderates the relationship, reflecting gendered patterns of altruism and succession expectations in the Chinese context.
