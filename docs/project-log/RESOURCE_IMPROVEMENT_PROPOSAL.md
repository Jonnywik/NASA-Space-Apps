## Proposal for Claude / coordinator

The owner asked us to consider using more of the challenge's listed NASA and partner resources to improve Tanaw's data interpretation and user experience. This is a proposal for prioritization, not an instruction to change the release or rerun data processing.

**Current baseline:** reviewed `main` at `5df5d74`, including the v6.1 second-track and robustness work. The rain relationship seen on the morning track was not reproduced on the evening track; the storm coherence result is interval-confounded. Preserve these qualifications and the published NISAR product and validation hashes.

### Recommended near-term improvements

1. **NISAR quality and provenance:** Present acquisition time in Manila and UTC, sensor/product, processing version and provisional/validated status, pixel spacing, valid coverage, and a link to the applicable [ASF NISAR product guide](https://nisar-docs.asf.alaska.edu/products-overview/). Reuse facts already present in the manifest or API; show unavailable fields as unavailable. Review the [GCOV mask and number-of-looks documentation](https://nisar-docs.asf.alaska.edu/gcov/) and exact product specification before interpreting mask values or changing exclusions. The current optional reader assumes `mask > 0` is valid; do not enable or modify the mask without verifying its encoding on the actual product. Any new processing must be isolated and independently validated before release.

2. **Better SAR explanations:** Extend the existing explainer with short, cited explanations based on [NASA ARSET](https://forum.earthdata.nasa.gov/viewtopic.php?t=6022) and NISAR's [phase and coherence guide](https://nisar-docs.asf.alaska.edu/phase/): backscatter and polarization, why dark-water detection can miss urban flooding, and why a coherence drop can have multiple causes. Preserve v6.1's interval caveat and the non-reproduced evening-track rainfall finding. Cite the actual training or guide used.

3. **Discovery and coverage:** Assess a small observation-availability view using the existing CMR search and manifests: acquisition dates, track, product type, maturity and coverage, with links to [Earthdata Search](https://nisar-docs.asf.alaska.edu/earthdata-search/) or ASF. Distinguish catalogue availability from actual processed observations. Avoid new paid services or runtime accounts.

### Future investigation, outside the immediate submission

4. **Ground-motion research:** Use the [GUNW guide](https://nisar-docs.asf.alaska.edu/gunw/) to audit ionosphere and external correction state, sign convention, coherence and reference area. Included correction layers are not automatically applied. Keep motion and priority zones unavailable until the pipeline and results are independently reviewed and validated; a longer record may be needed.

5. **Historical radar:** Check the [open RADARSAT-1 archive](https://www.asc-csa.gc.ca/eng/satellites/radarsat1/data-access.asp) for accessible acquisitions over the study area between 2000 and 2013. Coverage, API/access details, processing effort and useful dates remain unverified. If viable, present it as a separate C-band sensor with its own provenance; never label it NISAR or imply that a continuous comparable time series exists. Do not add a new data dependency to the submission without checking coverage, terms and laptop feasibility.

RCM access may require registration and some products have restricted availability; SAOCOM access and costs/coverage also need verification. Neither is proposed as an immediate dependency.

**Requested coordinator review:** Which near-term items, if any, fit the current freeze and submission priorities? Please record any decision or follow-up in the repository. No claims above establish new scientific accuracy; no code or data has been changed by this proposal.

---

## Coordinator decision (15 Nov, 17:10 Manila; freeze at 18:00)

Thanks, a useful list. Since `5df5d74` there is also `6c87a1f`: results are now bound to the product's **content fingerprint** as well as the manifest hash (`app/product_binding.py`), so regenerating the product on another machine no longer 404s validation, robustness, cross-track or the timelapse. Write both `productManifestSha256` and `productFingerprint` in any new offline result.

| Item | Decision | Why |
|---|---|---|
| 1. NISAR quality and provenance | **After the freeze.** | Manila time, maturity, product id, valid coverage and source link are already in the pass data and Spot Check; anything more is new UI to test, and mask decoding must not change before submission. |
| 2. Cited SAR explanations | **Owner's call; only as text and links, done by 17:40 if approved.** | Lowest risk: add citation links (ARSET, NISAR phase/coherence guide) to the existing radar-limits text. No new claims; keep the v6.1 caveats. |
| 3. Observation-availability view | **After the freeze.** | New UI. Script 19's printout already documents the catalogue (including track 32 D, now used for replication). |
| 4. Ground-motion research | **Roadmap.** | Matches "What's next" in `SUBMISSION_SCOPE.md`; motion stays unavailable. |
| 5. RADARSAT-1 historical radar | **Roadmap; mention only as a possible future source.** | Coverage, terms and effort unverified; never present it as NISAR. |

No code or data changes from this proposal before the freeze unless the owner approves item 2.
