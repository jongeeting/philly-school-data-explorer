# Questions for the School District

Open data gaps that someone at the district could close. Generated from [sources/gaps.csv](../sources/gaps.csv) (`district_question`); full entries are in [DATA_GAPS.md](DATA_GAPS.md).

1. **When a school closes or merges, does the district record which school(s) received its students (for example in Board resolutions or a closure crosswalk)? Is there a list for the 2013 closures?** (GAP-001, high priority)
   - Context: School lineage (predecessor/successor) table is empty: no source says which school absorbed a closed school's students
2. **Is there a building inventory that links school codes (ULCS) to buildings and OPA parcel numbers, including co-locations and annexes?** (GAP-013, high priority)
   - Context: No building table yet; schools are linked to City parcels (OPA account) by location, but not to buildings
3. **Does the district keep a history of canceled and late buses, or on-time performance by route? Could it be shared?** (GAP-021, high priority)
   - Context: Daily canceled or late bus list: no public history, and we have not started capturing it
4. **Could the facilities planning dashboard data (condition, program alignment, utilization, vulnerability scores, and recommendations) be published as a downloadable file?** (GAP-022, high priority)
   - Context: Facilities dashboard (scores for building condition, program alignment, utilization, neighborhood vulnerability, plus per-school recommendations) runs in a Qlik app with no export; scripted access is refused
5. **Which operational data exist internally but are not published: work order completion, bus on-time history, substitute fill rates, IEP evaluation timeliness?** (GAP-024, high priority)
   - Context: Maintenance work orders, bus on-time history, substitute fill rates, and IEP evaluation timeliness are not public
6. **Would the district confirm in writing that a public, attributed, openly licensed compilation of its open data sets is permitted under its Terms of Use (or agree to a short data-sharing note)?** (GAP-028, high priority)
   - Context: District Terms of Use restrict copying and limit use to governmental, accountability, and evaluative purposes; OpenDataPhilly lists the license as unspecified
7. **Have the minutes for the April 23 and April 30, 2026 Board meetings been approved and posted?** (GAP-037, high priority)
   - Context: Board minutes for the April 23 and April 30, 2026 meetings (the facilities plan vote) are not posted; the May 28 approval item has no attachment
8. **Why do the 2019-20 to 2024-25 master lists include only 2 to 4 'Alternate Schools' when 2018-19 and 2025-26 list 25 to 28? Is there a fuller list for those years?** (GAP-006, medium priority)
   - Context: District master lists omit most Alternate Schools in 2020-2025 (2 to 4 programs vs 25 to 28 in 2019 and 2026)
9. **Has the district ever reassigned a retired ULCS code to a new school?** (GAP-008, medium priority)
   - Context: Unknown whether the district ever reassigns a retired ULCS code to a new school
10. **Is there a list of school opening and closing dates (or Board resolution dates) beyond the Year Opened / Year Closed fields?** (GAP-009, medium priority)
   - Context: Closure and opening dates come only from list presence; real-world dates are not recorded
11. **What changed in the August 2025 repost of the 2014-15 to 2018-19 enrollment files, beyond the new suppression rules?** (GAP-020, medium priority)
   - Context: Student groups under 20 are suppressed at source; enrollment files for 2014-15 to 2018-19 were reposted Aug 2025 under new suppression rules
12. **When will staff vacancies, the SPOTlight scorecard, and Pre-K sites be refreshed?** (GAP-025, medium priority)
   - Context: Staff vacancies (due Aug 2025), SPOTlight scorecard (due spring 2025), and Pre-K sites (due spring 2026) are past the district's promised refresh dates
13. **Are the Goals and Guardrails progress figures available as data rather than PDFs?** (GAP-026, medium priority)
   - Context: Goals and Guardrails results are PDFs, with targets reset in April 2024
14. **Can catchment retention be published by grade or level (ES, MS, HS), or with residence at a smaller geography than catchment?** (GAP-031, medium priority)
   - Context: Catchment retention (students by catchment and school, SY 2016-17 on) is aggregated by catchment, not neighborhood, and cannot show where students went after the 2013 closures
15. **Are the facility condition assessment reports after 2022 available, and is there a structured version of the condition scores?** (GAP-032, medium priority)
   - Context: Building condition reports (FCA): 2020-22 reports are PDFs on Google Drive (about 78), 2017 reports and 2018-19 AHERA survive only on the Wayback Machine; the 2022-24 facilities site's API data was never archived
16. **When will catchment boundaries for 2025-26 and 2026-27 be published?** (GAP-034, medium priority)
   - Context: Catchments for SY 2025-26 and 2026-27 are not published (latest is 2024-25)
17. **Does the district have the March 7, 2013 SRC school closure resolution and minutes?** (GAP-038, medium priority)
   - Context: The SRC's March 7, 2013 school closure resolution PDF is not archived (Wayback 404); no minutes found for that meeting
18. **The 2010-11 enrollment file reports zero Black, Hispanic, American Indian, and multiracial students in every school. Is a corrected file available?** (GAP-044, medium priority)
   - Context: The district's 2010-11 enrollment file reports zero Black, Hispanic, American Indian, and multiracial students in every school; those values are withheld
19. **Grades 3-8 PSSA proficiency fell about 8 points citywide between 2010-11 and 2011-12. Is there a district note on what changed that year (for example, testing procedures)?** (GAP-048, medium priority)
   - Context: District grades 3-8 proficiency fell about 8 points citywide between 2010-11 and 2011-12 (math 59.1% to 50.9%); the cause is not documented in the data files
20. **Do alternative and contracted programs have NCES codes? About 25 per year have none in the master lists.** (GAP-004, low priority)
   - Context: NCES codes lost to scientific notation in CSV lists were repaired from xlsx where available or bridged from adjacent years; remaining blanks (about 25 per year in 2018, 2019, 2026, 2027) are programs with no NCES code in the source
21. **About 39 school-years in the master lists have no SRC School ID. Is that expected for those programs?** (GAP-005, low priority)
   - Context: Missing SRC school IDs (39 staged rows)
22. **Could Board meeting recordings be made downloadable or captioned, or shared for transcription?** (GAP-039, low priority)
   - Context: Board meeting video has no transcripts or captions and cannot be downloaded
23. **Is there a complete list of Board and SRC meeting videos (about 28 are not reachable from the player's listings)?** (GAP-042, low priority)
   - Context: 28 of 320 videos on the district TelVue player are not reachable from its listing pages (playlists show at most 50, no pagination); most are SRC meetings
24. **What was the ULCS code for Ombudsman South Transition (SRC 848, 2010-12)?** (GAP-045, low priority)
   - Context: Ombudsman South Transition (2010-11 and 2011-12) has an SRC school ID that maps to no ULCS code, so its enrollment is unassigned
