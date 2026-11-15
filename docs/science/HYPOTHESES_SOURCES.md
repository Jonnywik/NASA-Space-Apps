# Hypotheses and checked sources

These are hypotheses for investigation, not findings established by Tanaw. Spatial overlap does not prove cause. Filipino wording awaits native-speaker review.

1. Eco et al. (2020), *Disaster in Slow Motion*, JSM Environmental Science & Ecology 8(1):1068. [Paper](https://www.jscimedcentral.com/journal-article-info/JSM-Environmental-Science-and-Ecology/Disaster-in-Slow-Motion:-Widespread-Land-Subsidence-in-and-Around-Metro-Manila,-Philippines-Quantified-By-Insar-Time-Series-Analysis-5350). The authors attribute subsidence in and around CAMANAVA principally to groundwater over-extraction and discuss increased exposure to floods and tides. Their historical regional analysis does not establish the cause at each Tanaw pixel.
2. Maynilad Water Services, *Valenzuela Sewerage System Environmental Assessment*, section on tidal control gates, [World Bank document E2677 V8](https://documents.worldbank.org/curated/en/169381468295521077/pdf/E26770V80P113800Box385202B00PUBLIC0.pdf), p. 49. It describes gates closing at high tide to prevent entry and opening at low tide for drainage. This supports a plausible tidal mechanism, not proof of flood duration in a particular event.
3. US Environmental Protection Agency, [Urbanization – Hydrology](https://www.epa.gov/caddis/urbanization-hydrology). It describes reduced infiltration and increased runoff associated with impervious surfaces. This general mechanism is not a measurement of local runoff.

Fishpond conversion and coastal land-use effects on flood persistence were dropped: the sources reviewed did not establish this particular causal relationship for the study area. A broad claim that subsidence increases both flood frequency and duration was narrowed to increased flood exposure: the checked paper supports the latter but does not quantify those two outcomes.

```json
[
  {
    "id": "groundwater-subsidence",
    "title": "Hypothesis: groundwater extraction and ground motion",
    "titleFil": "Haypotesis: pagkuha ng tubig sa ilalim ng lupa at paggalaw ng lupa",
    "statement": "Groundwater over-extraction may contribute to land subsidence in CAMANAVA and the Bulacan coast.",
    "statementFil": "Maaaring mag-ambag sa paglubog ng lupa sa CAMANAVA at baybayin ng Bulacan ang labis na pagkuha ng tubig sa ilalim ng lupa.",
    "evidenceInApp": "Ground motion (N3)",
    "references": [{"citation": "Eco et al. (2020), Disaster in Slow Motion, JSM Environmental Science & Ecology 8(1):1068", "url": "https://www.jscimedcentral.com/journal-article-info/JSM-Environmental-Science-and-Ecology/Disaster-in-Slow-Motion:-Widespread-Land-Subsidence-in-and-Around-Metro-Manila,-Philippines-Quantified-By-Insar-Time-Series-Analysis-5350", "quote": "due mainly to over-extraction of groundwater"}]
  },
  {
    "id": "subsidence-flood-exposure",
    "title": "Hypothesis: subsidence and flood exposure",
    "titleFil": "Haypotesis: paglubog ng lupa at pagkakalantad sa baha",
    "statement": "Land subsidence may increase exposure to flooding and tidal incursions in coastal Metro Manila.",
    "statementFil": "Maaaring tumaas ang pagkakalantad sa baha at pagpasok ng tubig-dagat dahil sa paglubog ng lupa sa baybayin ng Metro Manila.",
    "evidenceInApp": "Ground motion (N3) and flood rhythm (N1)",
    "references": [{"citation": "Eco et al. (2020), Disaster in Slow Motion, JSM Environmental Science & Ecology 8(1):1068", "url": "https://www.jscimedcentral.com/journal-article-info/JSM-Environmental-Science-and-Ecology/Disaster-in-Slow-Motion:-Widespread-Land-Subsidence-in-and-Around-Metro-Manila,-Philippines-Quantified-By-Insar-Time-Series-Analysis-5350", "quote": "worsening floods and tidal incursions"}]
  },
  {
    "id": "tidal-drainage",
    "title": "Hypothesis: tides and drainage",
    "titleFil": "Haypotesis: pagtaas ng tubig-dagat at daluyan ng tubig",
    "statement": "High tides and river backflow may delay drainage in Malabon and Navotas.",
    "statementFil": "Maaaring maantala ang pagdaloy ng tubig sa Malabon at Navotas dahil sa pagtaas ng tubig-dagat at pagbalik ng tubig sa ilog.",
    "evidenceInApp": "Flood rhythm (N1)",
    "references": [{"citation": "Maynilad Water Services, Valenzuela Sewerage System Environmental Assessment, p. 49, World Bank E2677 V8", "url": "https://documents.worldbank.org/curated/en/169381468295521077/pdf/E26770V80P113800Box385202B00PUBLIC0.pdf", "quote": "During high tide, the gates are closed"}]
  },
  {
    "id": "impervious-runoff",
    "title": "Hypothesis: urban surfaces and runoff",
    "titleFil": "Haypotesis: mga ibabaw sa lungsod at pag-agos ng tubig-ulan",
    "statement": "Urban expansion and impervious surfaces may increase runoff.",
    "statementFil": "Maaaring dumami ang tubig-ulang umaagos sa ibabaw dahil sa paglawak ng lungsod at mga ibabaw na hindi nasisipsipan ng tubig.",
    "evidenceInApp": "Flood rhythm (N1) and rainfall history",
    "references": [{"citation": "US Environmental Protection Agency, Urbanization – Hydrology", "url": "https://www.epa.gov/caddis/urbanization-hydrology", "quote": "Decreased infiltration and increased surface runoff"}]
  }
]
```


## Candidate references from the Antigravity branch (NOT yet verified; not in the app)

The Antigravity agent researched the same task on branch `antigravity/codex-tasks-t3-t7`. Its additional references are listed here **for a team member to check by opening each link** before any is added to `frontend/public/hypotheses.json`. Until checked, they are not used in the app. The coordinator could not open DOI links from the cloud session, and the DOI for Lagmay et al. (2017) in particular should be confirmed against the journal page.

| Hypothesis | Candidate reference | Link |
|---|---|---|
| Groundwater extraction drives subsidence | Rodolfo & Siringan (2006), *Disasters* 30(1):118–139 | https://doi.org/10.1111/j.1467-9523.2006.00310.x |
| Subsidence increases flooding | Sulapas et al. (2024), *Int. J. Applied Earth Observation and Geoinformation* 133:104107 (reported max ~109 mm/yr in Bulacan, 2014–2020) | https://doi.org/10.1016/j.jag.2024.104107 |
| Subsidence increases flooding | Rodolfo et al. (2003), *Philippine Sociological Review* 51:17–40 | https://www.jstor.org/stable/44243070 |
| **Fishpond conversion affects drainage** (dropped by Codex for weak support) | Lagos et al. (2022), *Flooding and Subsidence Research: Bulacan Province* (technical report) | https://www.researchgate.net/publication/369742698_Flooding_and_Subsidence_Research_Bulacan_Province_Northern_Manila_Bay_Area_Philippines |
| Fishpond conversion affects drainage | Royal HaskoningDHV, RVO, Wetlands International, Ecoshape (2022), *North Manila Bay Flood Protection Strategy* | https://northmanilabayfps.ireport.royalhaskoningdhv.com/ |
| Tides and river backflow | JICA, CTI Engineering, Nippon Koei (2010), *Preparatory Study for Sector Loan on Disaster Risk Management* | https://openjica.jica.go.jp/metadb/up/JICA_LTD/11999380_01.pdf |
| Tides and river backflow | Tyree et al. (2013), *Effectiveness of CAMANAVA Flood Control Project*, J. Int. Development and Cooperation 19(3) | https://doi.org/10.15027/35045 |
| Impervious surfaces and runoff | World Bank & AIIB (2017), *Metro Manila Flood Management Project* (P153814) | https://www.aiib.org/en/projects/details/2017/approved/Philippines-Metro-Manila-Flood-Management-Project.html |
| Impervious surfaces and runoff | Lagmay et al. (2017), *Street floods in Metro Manila and possible solutions*, J. Environmental Sciences 59:39–47 (**confirm DOI**) | https://doi.org/10.1016/j.jes.2017.03.004 |

To adopt one: open the link, confirm the citation and that the source actually supports the statement, copy a short exact quote, then add it to the matching entry in `frontend/public/hypotheses.json`.
