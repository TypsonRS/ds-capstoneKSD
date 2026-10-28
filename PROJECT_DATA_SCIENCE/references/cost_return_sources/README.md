# Sources for the "Cost and return" cell (AgroRestoreAI.ipynb, section 11)

Downloaded 2026-10-28.

| File | Source | Used for |
|---|---|---|
| 01_IPCC_2019_Refinement_Vol4_Ch04_Forest_Land.pdf | https://www.ipcc-nggip.iges.or.jp/public/2019rf/pdf/4_Volume4/19R_V4_Ch04_Forest%20Land.pdf | `AGB_GROWTH_T_DM` = 3.9 (Table 4.9, p. 4.34), `ROOT_SHOOT` = 0.332 (Table 4.4, p. 4.18) |
| 01b_IPCC_2006_Vol4_Ch04_Forest_Land.pdf | https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/4_Volume4/V4_04_Ch4_Forest_Land.pdf | `CARBON_FRACTION` = 0.47 (Table 4.3, p. 4.48, tropical and subtropical) |
| 02_EcosystemMarketplace_State_of_VCM_2023.pdf | https://3298623.fs1.hubspotusercontent-na1.net/hubfs/3298623/SOVCM%202023/2023-EcoMarketplace_SOVCM-Nov28_FINALrev-Mar2024.pdf | `CARBON_PRICE` = 15.6 USD/t (Table 4, ARR credits 2023) |
| 03_FAO_AUDA-NEPAD_2021_Review_FLR_Africa.pdf | https://openknowledge.fao.org/server/api/core/bitstreams/e9662d8c-0dc1-444b-a7af-c18947c2a8ce/content | `FOREST_EST_COST` = 680 USD/ha (p. 61: Madagascar 680, Ethiopia 87-1,445, FMNR 40-50) |
| 04_TrillionTrees_Real_Cost_of_Restoring_Forests.pdf | https://trilliontrees.org/wp-content/uploads/2022/08/Trillion-Trees_Defining-the-real-cost-of-restoring-forests.pdf | `FOREST_MAINT_COST` / `FOREST_MAINT_YRS` (p. 20, Table 1, adapted from Bodin et al. 2021, FAO) |
| 05_WorldBank_TGO_cereal_yield_AG.YLD.CREL.KG.json | https://api.worldbank.org/v2/country/TGO/indicator/AG.YLD.CREL.KG?format=json | `CROP_YIELD_KG_HA` = 1,198 (2024; source: FAO) |
| 05_WorldBank_TGO_exchange_rate_PA.NUS.FCRF.json | https://api.worldbank.org/v2/country/TGO/indicator/PA.NUS.FCRF?format=json | `XOF_PER_USD` = 600 |
| 06_WFP_food_prices_TGO.csv, 06_WFP_markets_TGO.csv | https://data.humdata.org/dataset/wfp-food-prices-for-togo | `CROP_PRICE_XOF_KG` = 231 (median retail maize, Centrale, 2021-2026) |
| 07_LaCinquieme_rentabilite_mais_Togo.html | https://www.lacinquieme.tg/togo-quelle-est-la-rentabilite-de-la-production-du-mais/ | `CROP_COST_XOF_HA` = 96,700 FCFA/ha (2022) |
| 08_TogoDailyNews_DSID_revenu_net_mais.html | http://togodailynews.tg/agriculture-la-culture-du-mais-genere-un-revenu-moyen-net-de-223-000-fcfa-par-ha/ | Cross-check: DSID net income 223,000 FCFA/ha |
| 09_Agridigitale_filiere_mais.html | https://agridigitale.com/article/comment_rendre_la_filire_mas_plus_comptitive_ | Support for `FARMGATE_SHARE` (producer price <= 180 FCFA/kg) |
| 10_Hounkpati_2024_Frontiers_FLR_Central_Togo.pdf / .html | https://www.frontiersin.org/journals/sustainable-food-systems/articles/10.3389/fsufs.2024.1425797/full | Context: agroforestry return 417,000 FCFA/ha/yr in Central Togo (not used in the model) |

## Site extras (distance, slope, fire, soil acidity)

| File | Source | Used for |
|---|---|---|
| 11_Amegbeto_FAO_rentabilite_culture_manuelle_attelee_Togo.htm | https://openknowledge.fao.org/server/api/core/bitstreams/ba0b8e56-4d46-4782-b510-450f3aac050e/content/x5455b0q.htm | `CROP_LABOUR_DAYS` = 88 person-days/ha (Table 9, manual maize), `CLEARING_DAYS` = 30 (Table 14: 12,000-18,000 FCFA/ha at SMAG 499 FCFA/day) |
| 12_Hine_2014_WorldBank_SSATP_WP100_rural_transport.pdf | https://documents1.worldbank.org/curated/en/127531467999362783/pdf/937790NWP0Box30l0Transport0Planning.pdf | `HEADLOAD_USD_TKM` = 1.5 (p. 43, Starkey et al. 2002; trucks on rural roads 0.2 USD/t-km) |
| 13_Critchley_1991_Looking_after_our_land_technical.htm | https://www.fao.org/4/X5301E/x5301e0a.htm | `BUND_DAYS` = 75 (stone bunds: 50-100 person-days/ha) |
| 14_Jaleta_2024_AfJARE_lime_profitability.pdf | https://ageconsearch.umn.edu/record/347735/files/Is%20agricultural%20lime.pdf | `LIME_USD_T` = 107 (p. 7), `LIME_T_HA` = 0.86 (p. 6), `LIME_EFFECT_YRS` = 4 (p. 4) |
| 15_FAO_SFM_Toolbox_forest_restoration.html | https://www.fao.org/sustainable-forest-management-toolbox/modules/forest-restoration/en | `FOREST_LABOUR_DAYS` = 100 (50-150 person-days/ha, years 1-3) |
| 16_Barnes_2020_Ghana_fuel_management.pdf | https://koreascience.kr/article/JAKO202008848920259.pdf | `FIRE_TREAT_USD_HA` = 62.02 (prescribed burning; hand thinning 95.37) |
| 17_Togo_SMIG_SMAG_2023_BeninWebTV.html | https://beninwebtv.bj/togo-le-smig-et-smag-passent-a-52-500-fcfa-soit-une-augmentation-de-50/ | `WAGE_XOF_H` = 302.89 FCFA/h (SMIG = SMAG, 52,500 FCFA/month from 1 Jan 2023) |

Also used (not downloaded): Tobler (1993) hiking function, ~5 km/h walking speed on flat ground (`WALK_KMH`); `SEEDLINGS_HA` = 1,000 comes from file 04, p. 8.

Not downloaded: Bodin et al. 2021, Restoration Ecology 30: e13515 (https://doi.org/10.1111/rec.13515), which is quoted through file 04.
