# Filipino wording review

**Status: pending native-speaker review.** Proposed corrections below are drafts, not approval. Correct the meaning, keep every `{placeholder}` unchanged, and flag anything that sounds machine-translated. Leave blank corrections where no change is needed; review every row before sign-off. No source strings have been changed.

Video-priority sections come first: Story, mode names, Spot check, and Future (including the scenario caveat). The remaining strings follow by screen or shared function.

Some source text may itself require factual review before recording; translation review alone does not establish that claims are supported by observed data.

## Story

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `story.label` | Story | Kuwento |  |
| `story.step` | {i} of {n} | {i} sa {n} |  |
| `story.skip` | Skip tour | Laktawan ang tour |  |
| `story.close` | Close | Isara |  |
| `story.back` | Back | Balik |  |
| `story.next` | Next | Susunod |  |
| `story.done` | Done | Tapos na |  |
| `story.try` | Try it: find my barangay | Subukan: hanapin ang aking barangay |  |
| `story.keys` | Keys: ← → move, Esc closes. | Mga key: ← → para lumipat, Esc para isara. |  |
| `story.fact.passes` | {n} NISAR passes between {from} and {to}. | {n} na pass ng NISAR mula {from} hanggang {to}. |  |
| `story.fact.half` | {km2} km² flooded on half or more of the {n} passes. | {km2} km² ang binaha sa kalahati o higit pa ng {n} na pass. |  |
| `story.fact.motion` | {n} radar dates in the ground-motion series. | {n} petsa ng radar sa serye ng galaw ng lupa. |  |
| `story.fact.priority` | {pop} people live in the priority zones (exposure, not damage). | {pop} katao ang nakatira sa mga prayoridad na sona (exposure, hindi pinsala). |  |
| `story.1.title` | Our streets | Ang aming mga kalye |  |
| `story.1.body` | CAMANAVA and the Bulacan coast: Caloocan, Malabon, Navotas, Valenzuela, Obando, Meycauayan and Marilao. These streets flood most years. This season a satellite looked at them from space. | Ang CAMANAVA at ang baybayin ng Bulacan: Caloocan, Malabon, Navotas, Valenzuela, Obando, Meycauayan at Marilao. Binabaha ang mga kalyeng ito halos taon-taon. Ngayong panahon, tiningnan sila ng isang satellite mula sa kalawakan. |  |
| `story.2.title` | The season, pass by pass | Ang panahon, pass kada pass |  |
| `story.2.body` | NASA–ISRO's NISAR radar passes over about every 12 days and sees through cloud and at night. Watch water spread and drain from June to November 2026, with daily rainfall below. | Dumaraan ang radar na NISAR ng NASA–ISRO halos kada 12 araw at nakakakita kahit may ulap at sa gabi. Panoorin ang paglaganap at pagbaba ng tubig mula Hunyo hanggang Nobyembre 2026, kasama ang arawang ulan sa ibaba. |  |
| `story.3.title` | Flood rhythm | Ritmo ng baha |  |
| `story.3.body` | Some streets flooded once. Others flooded again and again. This map counts, for every place, how many passes saw water. | May mga kalyeng minsan lang binaha. Ang iba ay paulit-ulit. Binibilang ng mapang ito, sa bawat lugar, kung ilang pass ang nakakita ng tubig. |  |
| `story.4.title` | The ground beneath | Ang lupa sa ilalim |  |
| `story.4.body` | Radar can also measure tiny changes in distance to the ground. Orange shows ground moving away from the satellite over the season. This is line-of-sight motion, which can include sinking. | Nasusukat din ng radar ang maliliit na pagbabago ng distansya sa lupa. Ipinapakita ng kulay-dalandan ang lupang lumalayo sa satellite ngayong panahon. Ito ay galaw sa line of sight, na maaaring kasama ang paglubog. |  |
| `story.5.title` | Priority zones | Mga prayoridad na sona |  |
| `story.5.body` | Where frequent flooding and ground motion overlap, people are most exposed. The table counts people and buildings in those places: exposure, not damage. | Kung saan nagtatagpo ang madalas na baha at galaw ng lupa, mas nalalantad ang mga tao. Binibilang ng talaan ang mga tao at gusali sa mga lugar na iyon: exposure, hindi pinsala. |  |
| `story.6.title` | Check your barangay | Tingnan ang inyong barangay |  |
| `story.6.body` | Search for your barangay to see how many passes saw water at your spot, the rain around each pass and the ground-motion series. Copy the link to share it. | Hanapin ang inyong barangay para makita kung ilang pass ang nakakita ng tubig sa inyong lugar, ang ulan sa paligid ng bawat pass, at ang serye ng galaw ng lupa. Kopyahin ang link para maibahagi. |  |

## Mode names

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `mode.story` | Story | Kuwento |  |
| `mode.season` | Season | Panahon |  |
| `mode.rhythm` | Flood rhythm | Ritmo ng baha |  |
| `mode.motion` | Ground motion | Galaw ng lupa |  |
| `mode.history` | History | Kasaysayan |  |
| `mode.future` | Future | Hinaharap |  |

## Spot check

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `spot.noCount` | No flood count | Walang bilang ng baha |  |
| `spot.vegPasses` | Possible flooded vegetation (L-band) on {n} passes, not counted as open water. | Posibleng binahang halaman (L-band) sa {n} pass, hindi binibilang na bukas na tubig. |  |
| `spot.title` | Spot check | Spot check |  |
| `spot.close` | Close spot check | Isara ang spot check |  |
| `spot.copy` | Copy link | Kopyahin ang link |  |
| `spot.copied` | Link copied | Nakopya ang link |  |
| `spot.place` | Place | Lugar |  |
| `spot.barangay` | Barangay | Barangay |  |
| `spot.city` | City | Lungsod |  |
| `spot.noBarangay` | No barangay polygon here (open water, or outside every boundary) | Walang polygon ng barangay dito (bukas na tubig, o labas ng mga hangganan) |  |
| `spot.nisar` | NISAR flood record | Tala ng baha mula sa NISAR |  |
| `spot.permanent` | Permanent water: masked out, not counted as flooded. | Permanenteng tubig: inalis, hindi binibilang na baha. |  |
| `spot.floodCount` | Flooded on {k} of {n} valid passes | Binaha sa {k} sa {n} na wastong pass | Binaha sa {k} sa {n} wastong pass |
| `spot.cell` | Radar cell centre: {lat}°N, {lon}°E | Sentro ng radar cell: {lat}°N, {lon}°E |  |
| `spot.perPass` | State on each pass | Kalagayan sa bawat pass |  |
| `spot.state.water` | water | may tubig |  |
| `spot.state.dry` | dry | tuyo |  |
| `spot.state.nodata` | no valid data | walang wastong datos |  |
| `spot.state.water.short` | water | tubig |  |
| `spot.state.dry.short` | dry | tuyo |  |
| `spot.state.nodata.short` | no data | walang datos |  |
| `spot.db` | Radar values per pass | Mga halaga ng radar kada pass |  |
| `spot.state` | State | Kalagayan |  |
| `spot.noValue` | No value: the pass had no valid measurement here. | Walang halaga: walang wastong sukat ang pass na ito rito. |  |
| `spot.selected` | On the selected pass ({date}): {state}. | Sa napiling pass ({date}): {state}. |  |
| `spot.rain` | Rainfall around each pass | Ulan sa paligid ng bawat pass |  |
| `spot.rain.cell` | One NASA POWER grid cell for the whole area, not rain at this exact street. | Isang grid cell ng NASA POWER para sa buong lugar, hindi ang ulan sa mismong kalyeng ito. |  |
| `spot.rain.same` | Same day | Parehong araw |  |
| `spot.rain.p3` | Prior 3 days | Nakaraang 3 araw |  |
| `spot.rain.p7` | Prior 7 days | Nakaraang 7 araw |  |
| `spot.rain.missing` | Missing: no rainfall value for these days (not zero) | Nawawala: walang halaga ng ulan sa mga araw na ito (hindi zero) |  |
| `spot.rain.nopass` | The selected pass has no rainfall row. | Walang hanay ng ulan para sa napiling pass. |  |
| `spot.rain.all` | Rainfall for all passes | Ulan para sa lahat ng pass |  |
| `spot.rain.nopasses` | Waiting for the pass list. | Naghihintay ng listahan ng pass. |  |
| `spot.los` | Line-of-sight motion series | Serye ng galaw sa line of sight |  |

## Future and scenario caveat

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `future.scenario.bars` | Bars are the scenario's own rainfall for each month. Dots are the outlook's ensemble mean for the months the outlook covers. | Ang mga bar ay sariling ulan ng senaryo sa bawat buwan. Ang mga tuldok ay ensemble mean ng outlook sa mga buwang saklaw nito. |  |
| `future.scenario.envelope` | This is an upper envelope built from different years. It is not a year that happened. | Ito ay pinakamataas na hangganan na binuo mula sa iba't ibang taon. Hindi ito taong aktuwal na nangyari. |  |
| `future.scenario.powerCaveat` | Rainfall here is NASA POWER: one ~50 km grid cell from satellite-and-model reanalysis, not rain gauges. In the dry months (about December to April) it reads much wetter than other records for this area, so analog years such as 2020 show very high dry-season totals. Compare scenarios with each other and with the normal year, not as exact millimetres. | Ang ulan dito ay mula sa NASA POWER: isang grid cell na mga ~50 km mula sa reanalysis ng satellite at modelo, hindi mula sa mga rain gauge. Sa mga tag-tuyot na buwan (mga Disyembre hanggang Abril), mas mataas ang basa nito kaysa sa ibang talaan para sa lugar na ito, kaya napakataas ng tag-tuyot na kabuuan sa mga analog na taon tulad ng 2020. Ihambing ang mga senaryo sa isa't isa at sa karaniwang taon, hindi bilang eksaktong milimetro. | Ang ulan dito ay mula sa NASA POWER: isang grid cell na humigit-kumulang 50 km, batay sa reanalysis ng satellite at modelo, hindi sa mga rain gauge. Sa mga buwan ng tagtuyot (mga Disyembre hanggang Abril), mas mataas ang tinatayang ulan nito kaysa sa ibang talaan para sa lugar na ito, kaya napakataas ng kabuuan sa tagtuyot sa mga analog na taon tulad ng 2020. Ihambing ang mga senaryo sa isa't isa at sa karaniwang taon, hindi bilang eksaktong milimetro. |
| `future.outlook.title` | Seasonal rainfall outlook | Outlook sa pana-panahong ulan |  |
| `future.outlook.lead` | What a seasonal forecast model suggests for the coming months: a rainfall outlook, not a street-level forecast. | Ang iminumungkahi ng isang seasonal forecast model para sa susunod na mga buwan: outlook sa ulan, hindi forecast sa antas ng kalye. |  |
| `future.outlook.aria` | Chart of {n} outlook months with the spread between model members. | Tsart ng {n} buwan ng outlook kasama ang pagitan ng mga miyembro ng modelo. |  |
| `future.outlook.mean` | Ensemble mean | Ensemble mean |  |
| `future.outlook.spread` | Member range | Saklaw ng mga miyembro |  |
| `future.outlook.model` | Model | Modelo |  |
| `future.outlook.run` | Run date | Petsa ng run |  |
| `future.outlook.horizon` | Horizon | Saklaw ng panahon |  |
| `future.outlook.res` | Resolution | Resolusyon |  |
| `future.outlook.members` | Ensemble members | Mga miyembro ng ensemble |  |
| `future.months` | months | buwan |  |
| `future.outlook.note` | Dots are the ensemble mean. Bars show the spread between members: a wide bar means the members disagree. | Ang mga tuldok ay ensemble mean. Ipinapakita ng mga bar ang pagitan ng mga miyembro: ang malapad na bar ay nangangahulugang hindi nagkakasundo ang mga miyembro. |  |
| `future.scenario.title` | 12-month conditional scenarios | 12-buwang kondisyonal na senaryo |  |
| `future.scenario.lead` | Conditional scenarios, not predictions. Pick a rainfall pattern taken from history and see what it implies. | Kondisyonal na senaryo, hindi hula. Pumili ng padron ng ulan mula sa kasaysayan at tingnan ang ibig sabihin nito. |  |
| `future.scenario.pick` | Choose a scenario | Pumili ng senaryo |  |
| `future.scenario.aria` | Chart of monthly rainfall for the scenario {label}. | Tsart ng buwanang ulan para sa senaryong {label}. |  |
| `future.phase.obs` | Observed | Naobserbahan |  |
| `future.phase.outlook` | Outlook · {n} mo | Outlook · {n} bwn |  |
| `future.phase.scenario` | Scenario · {n} mo | Senaryo · {n} bwn |  |
| `future.phase.aria` | Which months are observed, outlook or scenario | Aling mga buwan ang naobserbahan, outlook o senaryo |  |
| `future.phase.note` | Observations end before {month}. Dashed = model outlook. Dotted = conditional scenario built from past years. | Natatapos ang mga obserbasyon bago ang {month}. Putol-putol na guhit = outlook ng modelo. Tuldok-tuldok = kondisyonal na senaryo mula sa mga nakaraang taon. |  |
| `future.boundary` | scenario starts | simula ng senaryo |  |
| `future.status.outlook` | Scenario value, month also covered by the outlook | Halaga ng senaryo, buwang saklaw din ng outlook |  |
| `future.status.scenario` | Conditional scenario month | Buwan ng kondisyonal na senaryo |  |
| `future.flood.title` | Flood scenario (exploratory) | Senaryo ng baha (eksploratoryo) |  |
| `future.exploratory` | Exploratory | Eksploratoryo |  |
| `future.flood.aria` | Chart of expected flooded area per month with low, base and high bands. | Tsart ng inaasahang binahang lawak kada buwan na may mababa, base at mataas na banda. |  |
| `future.flood.band` | Low to high | Mababa hanggang mataas |  |
| `future.flood.base` | Base | Base |  |
| `future.flood.legend` | Band = low to high under the stated assumptions; line = base. These are not probabilities and not a prediction of next year's floods. | Ang banda ay mababa hanggang mataas sa ilalim ng nakasaad na mga palagay; ang linya ay base. Hindi ito mga probabilidad at hindi hula sa mga baha sa susunod na taon. |  |
| `future.rel.title` | Rain-to-flood relationship (n = {n} passes) | Ugnayan ng ulan at baha (n = {n} na pass) |  |
| `future.rel.aria` | Scatter of flooded area against the prior 7-day rainfall for {n} passes. | Scatter ng binahang lawak laban sa ulan sa nakaraang 7 araw para sa {n} pass. |  |
| `future.rel.x` | prior 7-day rain (mm) | ulan sa nakaraang 7 araw (mm) |  |
| `future.motion.title` | Ground-motion projection | Proyeksyon ng galaw ng lupa |  |
| `future.projection.tip` | PROJECTION | PROYEKSYON |  |

## Season

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `season.title` | Season · flood extent by pass | Panahon · lawak ng baha kada pass |  |
| `season.lead` | NISAR (L-band radar) passes over CAMANAVA about every 12 days. Step through the passes to watch water spread and drain. | Dumaraan ang NISAR (radar na L-band) sa CAMANAVA halos kada 12 araw. Isa-isahin ang mga pass para makita ang paglaganap at pagbaba ng tubig. |  |
| `season.player.aria` | Season player. Left and right arrows step through passes. Space plays or pauses. | Player ng panahon. Ang kaliwa at kanang arrow ay lumilipat ng pass. Ang Space ay nagpe-play o nagpa-pause. |  |
| `season.acquired` | Acquired | Nakuha |  |
| `season.passOf` | Pass {i} of {n} | Pass {i} sa {n} |  |
| `season.prev` | Previous pass | Naunang pass |  |
| `season.next` | Next pass | Susunod na pass |  |
| `season.play` | Play | I-play |  |
| `season.pause` | Pause | I-pause |  |
| `season.keys` | Keyboard: focus this box, then ← → step, Home and End jump, Space plays or pauses. | Keyboard: i-focus ang kahong ito, saka ← → para lumipat, Home at End para tumalon, Space para mag-play o mag-pause. |  |
| `season.flooded` | Flooded area | Binahang lawak |  |
| `season.vegetation` | Possible flooded vegetation | Posibleng binahang halaman |  |
| `season.vegetation.note` | L-band double bounce; not added to open water | double bounce sa L-band; hindi idinadagdag sa bukas na tubig |  |
| `season.valid` | Valid pixels | Wastong pixel |  |
| `season.valid.note` | of the scene | ng eksena |  |
| `season.permanent` | Permanent water ({km2} km²) is masked out and not counted as flooded. | Ang permanenteng tubig ({km2} km²) ay inalis at hindi binibilang na baha. |  |
| `season.layers` | Layer | Layer |  |
| `season.layer.flood` | Flood mask | Mask ng baha |  |
| `season.layer.hh` | HH backscatter | HH backscatter |  |
| `season.layer.rgb` | Polarization RGB | RGB ng polarization |  |
| `season.legend` | Legend | Legend |  |
| `season.legend.rest` | Everything else: dry, permanent water (masked) or no valid data. | Lahat ng iba: tuyo, permanenteng tubig (inalis), o walang wastong datos. |  |
| `season.hh.note` | Raw HH radar brightness for this pass. Dark means a smooth surface such as calm water; bright means rough or built-up ground. This is not a classification. | Hilaw na liwanag ng HH radar sa pass na ito. Madilim ang makinis na ibabaw tulad ng tahimik na tubig; maliwanag ang magaspang o may gusali. Hindi ito klasipikasyon. |  |
| `season.chart.title` | Flooded area and rainfall | Binahang lawak at ulan |  |
| `season.chart.aria` | Chart of flooded area for {n} NISAR passes with daily rainfall between {from} and {to}. | Tsart ng binahang lawak para sa {n} pass ng NISAR kasama ang arawang ulan mula {from} hanggang {to}. |  |
| `season.rain` | NASA POWER rainfall | Ulan (NASA POWER) |  |
| `season.selected` | Selected pass | Napiling pass |  |
| `season.missingDays` | {n} rainfall days missing (gaps, not zeros) | {n} araw na walang datos ng ulan (puwang, hindi zero) |  |
| `season.table` | Table of passes | Talaan ng mga pass |  |
| `season.maturity` | Product maturity | Antas ng produkto |  |
| `season.rule` | How a pass is classified | Paano inuuri ang isang pass |  |
| `season.manila` | Manila time | Oras sa Maynila |  |

## Flood rhythm

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `rhythm.title` | Flood rhythm | Ritmo ng baha |  |
| `rhythm.lead` | For each place: on how many of this season's NISAR passes was water seen? Places that flood again and again stand out. | Sa bawat lugar: ilang beses nakitang may tubig sa mga pass ng NISAR ngayong panahon? Litaw ang mga lugar na paulit-ulit na binabaha. |  |
| `rhythm.passes` | Passes in the season | Bilang ng pass sa panahon |  |
| `rhythm.half` | Flooded on half or more of the passes | Binaha sa kalahati o higit pa ng mga pass |  |
| `rhythm.half.note` | area, permanent water excluded | lawak, hindi kasama ang permanenteng tubig |  |
| `rhythm.legend` | Legend: flooded on k of n passes | Legend: binaha sa k sa n na pass |  |
| `rhythm.k_of_n` | {k} of {n} passes | {k} sa {n} na pass |  |
| `rhythm.permanent` | Permanent water such as the bay is masked out, so it is not counted as flooded. Missing or invalid pixels are left out of the count for that place. | Inalis ang permanenteng tubig tulad ng look, kaya hindi ito binibilang na baha. Ang nawawala o di-wastong pixel ay hindi isinasama sa bilang ng lugar na iyon. |  |
| `rhythm.once` | Flooded at least once | Binaha kahit minsan |  |
| `rhythm.permanent.legend` | Permanent water (masked, grey) | Permanenteng tubig (inalis, abo) |  |

## Ground motion and priority

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `motion.title` | Ground motion · line of sight | Galaw ng lupa · line of sight |  |
| `motion.los` | Line-of-sight motion: the radar measures the change in distance along its slanted view, not straight down. It can only be called sinking if sideways motion is small. Positive means moving away from the satellite. | Galaw sa line of sight: sinusukat ng radar ang pagbabago ng distansya sa pahilis nitong tanaw, hindi tuwid pababa. Matatawag lang itong paglubog kung maliit ang pahalang na galaw. Ang positibo ay lumalayo sa satellite. |  |
| `motion.median.cum` | Median cumulative LOS motion | Median ng pinagsama-samang galaw sa LOS |  |
| `motion.median.rate` | Median LOS rate (extrapolated) | Median na bilis sa LOS (extrapolated) |  |
| `motion.positive` | positive = away from satellite | positibo = lumalayo sa satellite |  |
| `motion.epochs` | Radar dates (epochs) | Mga petsa ng radar (epochs) |  |
| `motion.span` | spanning {days} days | sumasaklaw ng {days} araw |  |
| `motion.cumulative` | This is cumulative line-of-sight displacement over {days} days, relative to the first date and to a reference area. | Ito ang pinagsama-samang displacement sa line of sight sa loob ng {days} araw, kumpara sa unang petsa at sa isang reference area. |  |
| `motion.extrapolation` | Any per-year figure extends a short record. It is an extrapolation, not a measured annual rate. | Ang anumang halaga kada taon ay pagpapahaba lamang ng maikling tala. Extrapolation ito, hindi sinukat na taunang bilis. |  |
| `motion.legend.cum` | Cumulative LOS motion | Pinagsama-samang galaw sa LOS |  |
| `motion.legend.rate` | LOS rate (extrapolated) | Bilis sa LOS (extrapolated) |  |
| `motion.away` | away from satellite | lumalayo sa satellite |  |
| `motion.toward` | toward satellite | papalapit sa satellite |  |
| `motion.near0` | near zero | malapit sa zero |  |
| `motion.ref.area` | Reference area | Reference area |  |
| `motion.ref.epoch` | Reference date | Petsa ng reference |  |
| `motion.epochs.list` | Dates | Mga petsa |  |
| `motion.corrections` | Corrections | Mga pagwawasto |  |
| `motion.corrections.none` | none applied | walang inilapat |  |
| `motion.geometry` | Geometry | Geometry |  |
| `motion.rhythmUnder` | Show flood rhythm beneath the motion layer | Ipakita ang ritmo ng baha sa ilalim ng layer ng galaw |  |
| `motion.click` | Click the map to see the motion series at that point. | Mag-click sa mapa para makita ang serye ng galaw sa puntong iyon. |  |
| `motion.tip` | LOS motion | Galaw sa LOS |  |
| `priority.title` | Priority zones | Mga prayoridad na sona |  |
| `priority.lead` | Places flooded on half or more of the passes where line-of-sight motion also shows ground moving away from the satellite beyond the noise threshold. Exposure, not damage. | Mga lugar na binaha sa kalahati o higit pa ng mga pass at kung saan ipinapakita rin ng galaw sa line of sight na lumalayo sa satellite ang lupa lampas sa antas ng ingay. Exposure, hindi pinsala. |  |

## History

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `hist.avail.title` | Data timeline since 2000 | Timeline ng datos mula 2000 |  |
| `hist.avail.lead` | Which dataset exists when. Move the slider under the map to check a date. | Alin ang may datos at kailan. Igalaw ang slider sa ilalim ng mapa para tingnan ang isang petsa. |  |
| `hist.now` | now | ngayon |  |
| `hist.catalogueOnly` | catalogue only (not loaded in Tanaw) | katalogo lang (hindi pa nakakarga sa Tanaw) |  |
| `hist.integrated` | integrated | nakakarga na |  |
| `hist.atDate.yes` | available at the chosen date | available sa napiling petsa |  |
| `hist.atDate.starts` | not at this date: starts {when} | wala sa petsang ito: nagsisimula sa {when} |  |
| `hist.atDate.ended` | not at this date: ended {when} | wala sa petsang ito: natapos noong {when} |  |
| `hist.nosplice` | Optical, C-band and L-band data are never merged into one numeric series. Today's population is never shown as if it were observed in 2000. | Hindi pinagsasama sa iisang serye ng numero ang optical, C-band at L-band. Hindi kailanman ipinapakita ang kasalukuyang populasyon na parang naobserbahan noong 2000. |  |
| `hist.monthly.title` | Monthly rainfall anomalies | Mga anomalya ng buwanang ulan |  |
| `hist.monthly.lead` | Monthly total compared with the {period} average for the same month. | Buwanang kabuuan kumpara sa average na {period} para sa parehong buwan. |  |
| `hist.monthly.missing` | A month with missing days has no anomaly and leaves a gap. Missing days are never counted as dry. | Ang buwang may nawawalang araw ay walang anomalya at nag-iiwan ng puwang. Hindi kailanman binibilang na tuyo ang nawawalang araw. |  |
| `hist.anomaly` | Anomaly | Anomalya |  |
| `hist.anomaly.aria` | Bar chart of monthly rainfall anomalies from {from} to {to}. | Bar chart ng mga buwanang anomalya ng ulan mula {from} hanggang {to}. |  |
| `hist.missingDays` | {n} days missing | {n} araw na nawawala |  |
| `hist.rank.title` | Where 2026 ranks | Saan nakapuwesto ang 2026 |  |
| `hist.rank.year` | Jun–Nov {year} rank | Ranggo ng Hun–Nob {year} |  |
| `hist.rank.complete` | season complete | kumpleto ang panahon |  |
| `hist.rank.incomplete` | season not complete | hindi pa kumpleto ang panahon |  |
| `hist.rank.total` | Season total | Kabuuan ng panahon |  |
| `hist.rank.aria` | Bar chart of June to November rainfall totals by year. {year} ranks {rank} of {of}. | Bar chart ng kabuuang ulan mula Hunyo hanggang Nobyembre kada taon. Ang {year} ay ika-{rank} sa {of}. |  |
| `hist.rank.partial` | The season is not finished: the rank compares 1 June to {date} with the same window in every other year, and it can still change. | Hindi pa tapos ang panahon: inihahambing ng ranggo ang 1 Hunyo hanggang {date} sa parehong saklaw ng bawat ibang taon, at maaari pa itong magbago. |  |
| `hist.rank.todate` | Total so far | Kabuuan sa ngayon |  |
| `hist.rank.window` | 1 Jun to {date} | 1 Hun hanggang {date} |  |
| `hist.rank.meaning` | {year} ranks {rank} of {of} since 2000, where 1 is the wettest. | Ang {year} ay ika-{rank} sa {of} mula 2000, kung saan 1 ang pinakamaulan. |  |
| `hist.rank.highlight` | {year} is the outlined bar. | Ang {year} ang bar na may balangkas. |  |
| `hist.trend.title` | Rainfall trend | Trend ng ulan |  |
| `hist.trend.slope` | Trend | Trend |  |
| `hist.trend.n` | Months used | Mga buwang ginamit |  |
| `hist.trend.sig` | The fitted trend is distinguishable from zero at the 95% level. | Naiiba sa zero ang fitted na trend sa 95% na antas. |  |
| `hist.trend.notsig` | The fitted trend is not distinguishable from zero at the 95% level. | Hindi naiiba sa zero ang fitted na trend sa 95% na antas. |  |
| `hist.trend.nocause` | A trend in one grid cell says nothing about its cause. | Walang sinasabi ang trend sa isang grid cell tungkol sa sanhi nito. |  |

## Limits

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `limits.button` | Limits | Mga limitasyon |  |
| `limits.inline` | Limitations ({n}) | Mga limitasyon ({n}) |  |
| `limits.title` | Limits of this view | Mga limitasyon ng view na ito |  |
| `limits.standing` | Always true | Laging totoo |  |
| `limits.fromApi` | From the data in view | Mula sa datos na nakikita |  |
| `limits.none` | No limitation strings loaded yet. | Wala pang nakargang limitasyon. |  |
| `limits.standing.1` | Some NISAR products used here are marked provisional and may be reprocessed. | Ang ilang produkto ng NISAR na ginagamit dito ay may markang provisional at maaaring iproseso muli. |  |
| `limits.standing.2` | Flood maps come from a threshold rule on radar brightness. Narrow streets and dense buildings can hide flooding, so flooded area in the city may be undercounted. | Ang mapa ng baha ay galing sa panuntunang threshold sa liwanag ng radar. Maaaring matakpan ng makikitid na kalye at siksik na gusali ang baha, kaya posibleng kulang ang bilang ng binahang lawak sa lungsod. |  |
| `limits.standing.3` | Line-of-sight (LOS) motion is measured along the satellite's slanted view, relative to a reference area. It is not straight-down sinking unless stated, and a few months of data cannot give a reliable yearly rate. | Ang galaw sa line of sight (LOS) ay sinusukat sa pahilis na tanaw ng satellite kumpara sa isang reference area. Hindi ito tuwid na paglubog maliban kung nakasaad, at hindi sapat ang ilang buwang datos para sa maaasahang taunang bilis. |  |
| `limits.standing.4` | Exposure counts people and buildings inside mapped zones. It is not damage, loss or risk to any person. | Binibilang ng exposure ang mga tao at gusali sa loob ng mapang sona. Hindi ito pinsala, pagkalugi, o panganib sa sinumang tao. | Binibilang ng exposure ang mga tao at gusali sa loob ng nakamapang sona. Hindi ito pinsala, pagkalugi, o panganib sa sinumang tao. |
| `limits.standing.5` | Rainfall comes from one coarse grid cell (NASA POWER). It is not rain on your street. | Ang ulan ay galing sa isang magaspang na grid cell (NASA POWER). Hindi ito ulan sa inyong kalye. |  |
| `limits.standing.6` | Outlooks and scenarios are conditional what-ifs built from model output and past years. They are not predictions of next year's floods. | Ang mga outlook at senaryo ay kondisyonal na what-if mula sa output ng modelo at mga nakaraang taon. Hindi ito hula sa mga baha sa susunod na taon. |  |
| `limits.standing.7` | Sentinel-1 (C-band, 2022–2025 events) and NISAR (L-band, 2026) are different sensors and years. They are never merged into one number. | Magkaibang sensor at taon ang Sentinel-1 (C-band, mga pangyayaring 2022–2025) at NISAR (L-band, 2026). Hindi sila kailanman pinagsasama sa iisang numero. |  |

## Radar cards

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `radar.button` | How radar sees | Paano nakakakita ang radar |  |
| `radar.title` | How radar sees | Paano nakakakita ang radar |  |
| `radar.close` | Close | Isara |  |
| `radar.remember` | Remember: | Tandaan: |  |
| `radar.water.title` | Why does water look dark? | Bakit madilim ang tubig? |  |
| `radar.water.p1` | A radar satellite sends its own microwave pulse and records the echo that comes back. It works day and night and sees through cloud. | Ang radar satellite ay nagpapadala ng sarili nitong microwave pulse at itinatala ang echo na bumabalik. Gumagana ito araw at gabi at nakakakita kahit may ulap. |  |
| `radar.water.p2` | Calm water is smooth, like a mirror. The pulse bounces away from the satellite instead of back to it, so very little echo returns and the pixel is dark. | Makinis ang tahimik na tubig, parang salamin. Tumatalbog palayo sa satellite ang pulse sa halip na bumalik, kaya kaunting echo lang ang bumabalik at madilim ang pixel. |  |
| `radar.water.p3` | Rough ground, trees and buildings scatter energy back, so they look brighter. Wind-roughened water can look bright, and a smooth road can look dark, so a dark pixel is a clue, not proof of flooding. | Ang magaspang na lupa, puno, at gusali ay nagpapabalik ng enerhiya, kaya mas maliwanag ang mga ito. Maaaring maliwanag ang tubig na ginagalaw ng hangin, at maaaring madilim ang makinis na kalsada, kaya palatandaan lang ang madilim na pixel, hindi patunay ng baha. |  |
| `radar.water.tip` | dark on a radar image usually means a smooth surface, such as calm water. | ang madilim sa larawan ng radar ay kadalasang makinis na ibabaw, gaya ng tahimik na tubig. |  |
| `radar.vegetation.title` | Why does flooded vegetation look bright in L-band HH? | Bakit maliwanag ang binahang halaman sa L-band HH? |  |
| `radar.vegetation.p1` | NISAR's L-band radar has a long wavelength, about 24 centimetres. It passes between leaves and reaches stems, trunks and the water below. | Mahaba ang wavelength ng L-band na radar ng NISAR, mga 24 na sentimetro. Dumaraan ito sa pagitan ng mga dahon at umaabot sa mga tangkay, katawan ng puno, at sa tubig sa ilalim. |  |
| `radar.vegetation.p2` | When water stands under plants such as rice, mangroves or reeds, the pulse can bounce off the water surface, then off a stem, and straight back to the satellite. This double bounce gives a very strong echo, especially in HH polarization (sent and received horizontally). | Kapag may nakatayong tubig sa ilalim ng mga halaman gaya ng palay, bakawan, o tambo, maaaring tumalbog ang pulse sa ibabaw ng tubig, saka sa isang tangkay, at diretsong bumalik sa satellite. Ang double bounce na ito ay nagbibigay ng napakalakas na echo, lalo na sa HH polarization (ipinapadala at tinatanggap nang pahalang). |  |
| `radar.vegetation.p3` | So flooded vegetation can look brighter than dry vegetation, the opposite of open water. Buildings also cause double bounce, which is one reason flooding between buildings in a dense city can be missed. | Kaya maaaring mas maliwanag ang binahang halaman kaysa tuyo, kabaligtaran ng bukas na tubig. Nagdudulot din ng double bounce ang mga gusali, kaya posibleng hindi makita ang baha sa pagitan ng mga gusali sa siksik na lungsod. |  |
| `radar.vegetation.tip` | bright can mean water under plants. Tanaw marks this separately as possible flooded vegetation, never as open water. | ang maliwanag ay maaaring tubig sa ilalim ng halaman. Hiwalay itong minamarkahan ng Tanaw bilang posibleng binahang halaman, hindi bilang bukas na tubig. |  |
| `radar.insar.title` | How does InSAR measure millimetres? | Paano nasusukat ng InSAR ang millimetro? | Paano nasusukat ng InSAR ang mga milimetro? |
| `radar.insar.p1` | A radar wave has a phase: where it is in its wave cycle when the echo returns. If the satellite passes the same place twice, the phase of the two echoes can be compared. | May phase ang radar wave: kung nasaan ito sa siklo ng alon pagbalik ng echo. Kung dalawang beses dadaan ang satellite sa iisang lugar, maihahambing ang phase ng dalawang echo. |  |
| `radar.insar.p2` | If the ground moved toward or away from the satellite between the two passes, the distance changed and the phase shifted. One full cycle of phase equals half a wavelength of movement, because the wave travels there and back. For L-band that is about 12 centimetres, so a small fraction of a cycle is a few millimetres. | Kung gumalaw ang lupa palapit o palayo sa satellite sa pagitan ng dalawang pass, nagbago ang distansya at nagbago ang phase. Ang isang buong siklo ng phase ay katumbas ng kalahating wavelength ng galaw, dahil papunta at pabalik ang alon. Sa L-band, mga 12 sentimetro iyon, kaya ang maliit na bahagi ng siklo ay ilang millimetro. |  |
| `radar.insar.p3` | The result is movement along the satellite's line of sight, measured relative to a reference area. The atmosphere and ionosphere can add errors, which is why Tanaw states which corrections were applied. | Ang resulta ay galaw sa line of sight ng satellite, sinusukat kumpara sa isang reference area. Maaaring magdagdag ng error ang atmospera at ionosphere, kaya sinasabi ng Tanaw kung aling mga pagwawasto ang inilapat. |  |
| `radar.insar.tip` | InSAR gives change along the line of sight. It does not automatically mean sinking. | pagbabago sa line of sight ang ibinibigay ng InSAR. Hindi ito awtomatikong paglubog. |  |
| `radar.bands.title` | L-band and C-band: what is the difference? | L-band at C-band: ano ang pagkakaiba? |  |
| `radar.bands.p1` | Radar bands are named by wavelength. NISAR's L-band is about 24 centimetres. Sentinel-1's C-band is about 5.6 centimetres. | Pinangangalanan ang mga band ng radar ayon sa wavelength. Mga 24 na sentimetro ang L-band ng NISAR. Mga 5.6 na sentimetro ang C-band ng Sentinel-1. |  |
| `radar.bands.p2` | Longer waves penetrate vegetation more deeply and stay coherent for longer. L-band holds up better for ground motion over fields and fishponds, and it sees water under plants. C-band mostly responds to the top of the canopy. | Mas malalim na tumatagos sa halaman ang mas mahabang alon at mas matagal na nananatiling coherent. Mas maaasahan ang L-band para sa galaw ng lupa sa mga bukid at palaisdaan, at nakakakita ito ng tubig sa ilalim ng halaman. Ang C-band ay higit na tumutugon sa tuktok ng mga dahon. |  |
| `radar.bands.p3` | Sentinel-1 has a long archive from 2014, which Tanaw uses as regional context. NISAR gives L-band for the 2026 season. Tanaw never merges the two into one number, because they see the ground differently. | May mahabang archive ang Sentinel-1 mula 2014, na ginagamit ng Tanaw bilang rehiyonal na konteksto. Nagbibigay ang NISAR ng L-band para sa panahon ng 2026. Hindi pinagsasama ng Tanaw ang dalawa sa iisang numero dahil magkaiba ang tingin nila sa lupa. |  |
| `radar.bands.tip` | L-band reaches deeper into vegetation. C-band reads the surface. | mas malalim ang abot ng L-band sa halaman. Ibabaw ang binabasa ng C-band. |  |

## Shared controls and other screens

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `app.tagline` | CAMANAVA 2026 · NISAR radar | CAMANAVA 2026 · radar ng NISAR |  |
| `nav.modes` | Views | Mga view |  |
| `regional.button` | Regional context | Rehiyonal na konteksto |  |
| `lang.label` | Language | Wika |  |
| `fixtures.banner` | SYNTHETIC DEV FIXTURES: the backend is not being used. Every number and image on this page is invented to test the layout. None of it is a result. | SYNTHETIC NA DEV FIXTURE: hindi ginagamit ang backend. Gawa-gawa lang ang bawat numero at larawan dito para subukan ang layout. Hindi ito resulta. |  |
| `map.aria` | Interactive map of CAMANAVA. Click a place for a spot check. | Interaktibong mapa ng CAMANAVA. Mag-click sa isang lugar para sa spot check. |  |
| `map.opacity` | Layer opacity | Linaw ng layer |  |
| `panel.findings` | Findings | Mga natuklasan |  |
| `panel.tabs` | Panel view | View ng panel |  |
| `panel.hide` | Hide panel | Itago ang panel |  |
| `panel.show` | Show panel | Ipakita ang panel |  |
| `panel.click` | Click anywhere on the map for a spot check of that place. | Mag-click kahit saan sa mapa para sa spot check ng lugar na iyon. |  |
| `kind.observed` | Observed | Naobserbahan |  |
| `kind.derived` | Derived | Kinuwenta |  |
| `kind.outlook` | Outlook | Outlook |  |
| `kind.scenario` | Scenario | Senaryo |  |
| `kind.synthetic` | Synthetic · not real data | Gawa-gawa · hindi totoong datos |  |
| `kind.observed.hint` | Measured by an instrument. | Sinukat ng isang instrumento. |  |
| `kind.derived.hint` | Calculated from observations by a stated rule. | Kinuwenta mula sa mga obserbasyon ayon sa nakasaad na panuntunan. |  |
| `kind.outlook.hint` | A model's rainfall guidance for the coming months, not a street-level forecast. | Gabay ng isang modelo sa ulan para sa susunod na mga buwan, hindi forecast sa antas ng kalye. |  |
| `kind.scenario.hint` | A conditional what-if built from history, not a prediction. | Kondisyonal na what-if mula sa kasaysayan, hindi hula. |  |
| `kind.synthetic.hint` | Invented test data. Not a result. | Gawa-gawang datos para sa pagsubok. Hindi resulta. |  |
| `kind.climate` | Climate | Klima |  |
| `kind.optical` | Optical | Optical |  |
| `kind.sar_c` | C-band radar | Radar na C-band |  |
| `kind.sar_l` | L-band radar | Radar na L-band |  |
| `kind.insar` | InSAR | InSAR |  |
| `kind.other` | Other | Iba pa |  |
| `src.label` | Source | Pinagmulan |  |
| `src.none` | not stated | hindi nakasaad |  |
| `src.resolution` | resolution | resolusyon |  |
| `chart.missing` | missing (not counted as zero) | nawawala (hindi binibilang na zero) |  |
| `missing.noTime` | time not reported | hindi iniulat ang oras |  |
| `missing.notReported` | not reported by the API | hindi iniulat ng API |  |
| `col.date` | Date | Petsa |  |
| `col.place` | Place | Lugar |  |
| `col.population` | People | Mga tao |  |
| `col.buildings` | Buildings | Mga gusali |  |
| `col.total` | Total | Kabuuan |  |
| `help.open` | How radar sees: open the explainer | Paano nakakakita ang radar: buksan ang paliwanag |  |
| `state.loading.title` | Loading… | Naglo-load… |  |
| `state.loading.body` | Waiting for the API. | Naghihintay sa API. |  |
| `state.unavailable.title` | Not available yet | Wala pa |  |
| `state.unavailable.body` | The API has no published data for this. Tanaw shows nothing rather than something invented. | Wala pang nailathalang datos ang API para dito. Mas mabuting walang ipakita ang Tanaw kaysa gawa-gawa. |  |
| `state.offline.title` | Backend not reachable | Hindi maabot ang backend |  |
| `state.offline.body` | The API did not answer. Start it in backend/ with: python -m uvicorn app.main:app --reload | Hindi sumagot ang API. Simulan ito sa backend/ gamit ang: python -m uvicorn app.main:app --reload |  |
| `state.error.title` | Something went wrong | May nagkamali |  |
| `state.error.body` | The API returned an unexpected error. | Nagbalik ang API ng hindi inaasahang error. |  |
| `state.outside.title` | Outside coverage | Labas sa saklaw |  |
| `state.outside.body` | This spot is outside the area this data covers. | Nasa labas ng saklaw ng datos na ito ang lugar na ito. |  |
| `state.upstream.title` | Upstream source unavailable | Hindi available ang pinagkukunan |  |
| `state.upstream.body` | The data provider behind this layer did not answer, so no value is shown. | Hindi sumagot ang pinagkukunan ng datos sa likod ng layer na ito, kaya walang ipinapakitang halaga. |  |
| `state.invalid.title` | Request or data rejected | Tinanggihan ang request o datos |  |
| `state.invalid.body` | The API rejected the request, or the data failed its checks. | Tinanggihan ng API ang request, o hindi pumasa ang datos sa mga pagsusuri. |  |
| `state.review.title` | Waiting for review | Naghihintay ng review |  |
| `state.review.body` | Results exist but have not passed review, so they are hidden. | May resulta na pero hindi pa pumapasa sa review, kaya nakatago. |  |
| `state.cachedAt` | A dated cache was served instead: {when}. | Naka-cache na may petsa ang ipinakita: {when}. |  |
| `swipe.title` | Compare two passes | Paghambingin ang dalawang pass |  |
| `swipe.enable` | Before / after swipe | Swipe bago / pagkatapos |  |
| `swipe.before` | Before | Bago |  |
| `swipe.after` | After | Pagkatapos |  |
| `swipe.position` | Divider position | Posisyon ng divider |  |
| `swipe.keys` | Keyboard: the divider on the map can be focused. ← → move it, Shift makes bigger steps, Home and End go to the edges. | Keyboard: maaaring i-focus ang divider sa mapa. ← → para ilipat, Shift para mas malaki ang hakbang, Home at End para sa mga gilid. |  |
| `swipe.divider` | Before and after divider | Divider ng bago at pagkatapos |  |
| `swipe.valuetext` | {before} on the left, {after} on the right. Divider at {pct} percent. | {before} sa kaliwa, {after} sa kanan. Nasa {pct} porsiyento ang divider. |  |
| `exposure.title` | Exposure by barangay | Exposure kada barangay |  |
| `exposure.lead.rhythm` | People and buildings inside places that flooded on half or more of the passes. | Mga tao at gusali sa mga lugar na binaha sa kalahati o higit pa ng mga pass. |  |
| `exposure.not_damage` | This is exposure, not damage: it counts what lies inside a mapped zone, not what was harmed. | Exposure ito, hindi pinsala: binibilang nito ang nasa loob ng mapang sona, hindi ang nasira. |  |
| `exposure.population` | People | Mga tao |  |
| `exposure.buildings` | Buildings snapshot | Snapshot ng mga gusali |  |
| `exposure.unassigned` | Exposed area outside every barangay polygon (for example sea): {km2} km². | Lawak na nasa labas ng bawat polygon ng barangay (hal. dagat): {km2} km². |  |
| `synthetic.banner` | SYNTHETIC DATA: the API marks these layers as synthetic demo data, not NISAR observations: {what}. Do not read them as results. | SYNTHETIC NA DATOS: minarkahan ng API ang mga layer na ito bilang gawa-gawang demo, hindi obserbasyon ng NISAR: {what}. Huwag basahin bilang resulta. |  |
| `fixtures.banner.nisar` | SYNTHETIC NISAR FIXTURES: flood passes, flood rhythm and ground motion on this page are invented to test the layout. Rainfall, outlook and places come from the real API. | SYNTHETIC NA NISAR FIXTURE: gawa-gawa lang ang mga pass ng baha, ritmo ng baha at galaw ng lupa sa pahinang ito para subukan ang layout. Galing sa totoong API ang ulan, outlook at mga lugar. |  |
| `time.history` | Date | Petsa |  |
| `time.history.avail` | Datasets available at the chosen date | Mga datos na available sa napiling petsa |  |
| `time.future` | Observations end, then outlook months, then conditional scenario months | Tapos ang mga obserbasyon, saka mga buwan ng outlook, saka mga buwan ng kondisyonal na senaryo |  |
| `time.passes` | NISAR passes | Mga pass ng NISAR |  |
| `time.pass` | Pass | Pass |  |
| `time.nopasses` | No passes loaded yet. | Wala pang nakargang pass. |  |
| `time.selected.note` | The selected pass is used in the Season view and in the spot check. | Ang napiling pass ay ginagamit sa view ng Panahon at sa spot check. |  |
| `stories.pin` | Our story | Aming kuwento |  |
| `search.label` | Find my barangay | Hanapin ang aking barangay |  |
| `search.placeholder` | Find my barangay or city… | Hanapin ang barangay o lungsod… |  |
| `search.results` | Matching places | Mga katugmang lugar |  |
| `search.none` | No match in the gazetteer. | Walang tugma sa gazetteer. |  |
| `search.level.barangay` | barangay | barangay |  |
| `search.level.city` | city | lungsod |  |
| `hyp.title` | Why might this be happening? | Bakit kaya ito nangyayari? |  |
| `hyp.lead` | Possible explanations to investigate. None of these is a proven cause. | Mga posibleng paliwanag na dapat siyasatin. Wala sa mga ito ang napatunayang sanhi. |  |
| `hyp.label` | Hypothesis | Hypothesis |  |
| `hyp.evidence` | Look at | Tingnan |  |

## Briefing, priority, validation and sources

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `briefing.title` | Place briefing | Buod para sa lugar |  |
| `briefing.facts` | Exports use the same point facts, sources and missing-data reasons as this card. | Ang mga export ay gumagamit ng parehong datos sa puntong ito, sanggunian, at dahilan ng nawawalang datos gaya ng card na ito. |  |
| `briefing.en` | Briefing (EN) | Buod (EN) |  |
| `briefing.fil` | Briefing (FIL) | Buod (FIL) |  |
| `briefing.csv` | Download CSV | I-download ang CSV |  |
| `briefing.review` | Filipino translation: pending your review. | Salin sa Filipino: hinihintay ang iyong pagsusuri. |  |
| `spot.priority.yes` | This point is inside a priority zone under the stated thresholds. | Nasa loob ng prayoridad na sona ang puntong ito ayon sa nakasaad na mga threshold. |  |
| `spot.priority.no` | This point is outside the priority zones under the stated thresholds. | Nasa labas ng mga prayoridad na sona ang puntong ito ayon sa nakasaad na mga threshold. |  |
| `spot.exposure.scope` | People and buildings in the priority zone within the containing barangay (not at this single point). | Mga tao at gusali sa prayoridad na sona sa loob ng barangay na kinaroroonan ng punto (hindi sa puntong ito lamang). |  |
| `validation.title` | Independent comparison | Paghahambing sa hiwalay na sanggunian |  |
| `validation.lead` | Agreement requires observed NISAR and a separate reference on a nearby date. Missing comparisons are not accuracy scores. | Kailangan ang aktuwal na obserbasyon ng NISAR at hiwalay na sanggunian sa malapit na petsa. Ang kawalan ng paghahambing ay hindi sukatan ng katumpakan. |  |
| `validation.pixels` | Jointly valid pixels | Mga pixel na parehong may wastong datos |  |
| `validation.accuracy` | Agreement fraction | Bahagi ng magkatugmang resulta |  |
| `sources.title` | Data sources and credits | Mga pinagkunan ng datos at pagkilala |  |

## Hypotheses

These are proposed explanations, not established causes. Review the four titles and summaries below; factual and reference verification is separate.

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `groundwater-subsidence.title` | Hypothesis: groundwater extraction and ground motion | Haypotesis: pagkuha ng tubig sa ilalim ng lupa at paggalaw ng lupa |  |
| `groundwater-subsidence.summary` | Groundwater over-extraction may contribute to land subsidence in CAMANAVA and the Bulacan coast. | Maaaring mag-ambag sa paglubog ng lupa sa CAMANAVA at baybayin ng Bulacan ang labis na pagkuha ng tubig sa ilalim ng lupa. |  |
| `subsidence-flood-exposure.title` | Hypothesis: subsidence and flood exposure | Haypotesis: paglubog ng lupa at pagkakalantad sa baha |  |
| `subsidence-flood-exposure.summary` | Land subsidence may increase exposure to flooding and tidal incursions in coastal Metro Manila. | Maaaring tumaas ang pagkakalantad sa baha at pagpasok ng tubig-dagat dahil sa paglubog ng lupa sa baybayin ng Metro Manila. |  |
| `tidal-drainage.title` | Hypothesis: tides and drainage | Haypotesis: pagtaas ng tubig-dagat at daluyan ng tubig | Haypotesis: pagtaas at pagbaba ng tubig-dagat at daluyan ng tubig |
| `tidal-drainage.summary` | High tides and river backflow may delay drainage in Malabon and Navotas. | Maaaring maantala ang pagdaloy ng tubig sa Malabon at Navotas dahil sa pagtaas ng tubig-dagat at pagbalik ng tubig sa ilog. |  |
| `impervious-runoff.title` | Hypothesis: urban surfaces and runoff | Haypotesis: mga ibabaw sa lungsod at pag-agos ng tubig-ulan |  |
| `impervious-runoff.summary` | Urban expansion and impervious surfaces may increase runoff. | Maaaring dumami ang tubig-ulang umaagos sa ibabaw dahil sa paglawak ng lungsod at mga ibabaw na hindi nasisipsipan ng tubig. |  |

## Backend briefing templates

These are separate from the UI dictionary. Correct the wording and retain placeholders exactly. The Filipino briefing remains pending native-speaker review.

| Key | English | Current Filipino | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `LABELS.place` | Place | Lugar |  |
| `LABELS.nisar` | Flood rhythm | Dalas ng pagbaha | Ritmo ng baha |
| `LABELS.rainfall` | Pass rainfall | Ulan sa mga pagdaan | Ulan sa bawat pass |
| `LABELS.motion` | Line-of-sight motion | Paggalaw sa line of sight |  |
| `LABELS.priority` | Priority zone | Priority zone | Prayoridad na sona |
| `LABELS.exposure` | Exposure | Exposure |  |
| `UNAVAILABLE` | not available because | hindi makuha dahil |  |
| `FLOOD` | flood count {count}; valid passes {valid} | bilang ng pagbaha {count}; valid na pagdaan {valid} | bilang ng pagbaha {count}; wastong mga pass {valid} |
| `PRIORITY_YES` | this point is in the priority zone | nasa priority zone ang puntong ito | nasa prayoridad na sona ang puntong ito |
| `PRIORITY_NO` | this point is outside the priority zone | wala sa priority zone ang puntong ito | nasa labas ng prayoridad na sona ang puntong ito |
| `EXPOSURE` | barangay exposure: {area} km², {population} people, {buildings} mapped buildings | exposure ng barangay: {area} km², {population} tao, {buildings} na nakamapang gusali |  |
| `RAINFALL` | {rain} mm in the seven days before the pass on {date} | {rain} mm sa pitong araw bago ang pagdaan noong {date} |  |
| `MOTION` | line-of-sight displacement {displacement} mm on {date}; positive values are away from the satellite | paggalaw sa line of sight: {displacement} mm noong {date}; ang positibong halaga ay palayo sa satellite |  |

### Additional export wording to review

- `render.py` supplies English fallback reasons (including “no reason was provided by the source”, “the source has no supported estimate”, “no complete prior-pass rainfall window is available”, and “no valid displacement epoch is available”). Source-provided reasons, warnings, limitations and field names may also be English. These need a translation strategy; do not invent translations for dynamic source text.
- The printable HTML uses English headings and notices: “Place briefing”, “Sources”, “Limitations”, “Translation: pending native-speaker review”, and “SYNTHETIC DEMO DATA”. Suggested Filipino: “Briefing ng lugar”, “Mga sanggunian”, “Mga limitasyon”, “Salin: naghihintay ng pagsusuri ng katutubong tagapagsalita”, and “SYNTHETIC NA DATOS PARA SA DEMO”. Keep the synthetic and pending-review notices visible.

## Coverage and placeholder check

- UI: 345 Filipino keys, 345 unique keys in the tables, including `Object.assign` additions; 0 lack an English counterpart.
- Hypotheses: 4 titles and 4 summaries, all included.
- Backend templates: 13 Filipino entries, all included.
- English/Filipino placeholder mismatches: UI 0, hypotheses 0, backend 0. Proposed corrections preserve their current placeholders.
- Check is mechanical; it does not verify meaning, source facts, naturalness, or native-speaker approval.

## Mangrove v2 UI strings (pending native review)

All v2 shell, Map tools, Spot card, findings summaries and timeline strings added for `DESIGN_SPEC_V2.md` are **pending native review**.

| Key | English | Current Filipino (pending native review) | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `header.area.season` | CAMANAVA · 2026 wet season | CAMANAVA · Panahon ng tag-ulan 2026 |  |
| `header.area.history` | CAMANAVA · 2000 – 2026 | CAMANAVA · 2000 – 2026 |  |
| `header.area.future` | CAMANAVA · Dec 2026 – Nov 2027 | CAMANAVA · Dis 2026 – Nob 2027 |  |
| `header.tour` | Take the tour | Sumama sa tour |  |
| `header.sources` | Sources and limits | Pinagmulan at limitasyon |  |
| `header.settings` | Settings: language, base map, units | Settings: wika, batayang mapa, mga yunit |  |
| `header.settings.mobile` | Settings: language, base map, tour, sources | Settings: wika, batayang mapa, tour, mga pinagmulan |  |
| `header.preview` | Pipeline preview (synthetic) | Pipeline preview (synthetic) |  |
| `header.regional` | Regional context (Sentinel-1 2022–2025) | Rehiyonal na konteksto (Sentinel-1 2022–2025) |  |
| `rail.layers` | Layers | Mga layer |  |
| `rail.rhythm.short` | Rhythm | Ritmo |  |
| `rail.motion.short` | Motion | Galaw |  |
| `demo.tag` | Demo | Demo |  |
| `demo.number` | Demo number | Halimbawang numero |  |
| `demo.title` | Synthetic demo data, not a NISAR observation | Gawa-gawang demo datos, hindi obserbasyon ng NISAR |  |
| `map.zoomIn` | Zoom in | Palakihin |  |
| `map.zoomOut` | Zoom out | Paliitin |  |
| `map.attribution` | © OpenStreetMap contributors · NISAR: NASA/ISRO via ASF | © OpenStreetMap contributors · NISAR: NASA/ISRO via ASF |  |
| `map.tools` | Map tools | Mga gamit sa mapa |  |
| `map.tools.open` | Map tools: map mode, overlay, layers | Mga gamit sa mapa: uri ng mapa, overlay, mga layer |  |
| `map.tools.mode` | Map mode | Uri ng mapa |  |
| `map.tools.mode.streets` | Streets | Mga kalsada |  |
| `map.tools.mode.minimal` | Minimal | Minimal |  |
| `map.tools.overlay` | Overlay | Overlay |  |
| `map.tools.overlay.one` | One at a time | Isa bawat pagkakataon |  |
| `map.tools.overlay.rhythm` | Flood rhythm (all passes) | Ritmo ng baha (lahat ng pass) |  |
| `map.tools.overlay.pass` | Single radar pass | Isang radar pass |  |
| `map.tools.overlay.motion` | Ground motion (InSAR) | Galaw ng lupa (InSAR) |  |
| `map.tools.overlay.scenario` | Flood scenario | Senaryo ng baha |  |
| `map.tools.showVeg` | Show possible flooded vegetation | Ipakita ang posibleng binahang halaman |  |
| `map.tools.layers` | Layers | Mga layer |  |
| `map.tools.layer.bgy` | Barangay boundaries | Mga hangganan ng barangay |  |
| `map.tools.layer.labels` | Place names | Pangalan ng lugar |  |
| `map.tools.layer.roads` | Major roads | Pangunahing kalsada |  |
| `map.tools.layer.rivers` | Rivers and coast | Mga ilog at baybayin |  |
| `map.tools.layer.study` | Study area outline | Balangkas ng lugar ng pag-aaral |  |
| `map.tools.layer.buildings` | Estimated buildings in flood zone | Tinatayang gusali sa binahang sona |  |
| `map.tools.layersCount` | {n} layers | {n} layer |  |
| `map.tools.reset` | Reset map | I-reset ang mapa |  |
| `map.tools.done` | Done | Tapos na |  |
| `map.swipe.handle` | Drag to compare Before and After | I-drag upang ihambing ang Bago at Pagkatapos |  |
| `search.v2.placeholder` | Find my barangay or city | Hanapin ang barangay o lungsod |  |
| `spot.selected.eyebrow` | SELECTED PLACE | NAPILING LUGAR |  |
| `spot.clear` | Clear spot selection | Alisin ang napiling lugar |  |
| `spot.briefing` | Briefing | Buod |  |
| `spot.csv` | CSV | CSV |  |
| `spot.fullDetails` | Full details | Buong detalye |  |
| `spot.backToFindings` | Back to area findings | Bumalik sa mga natuklasan |  |
| `spot.card.waterPasses` | Water on NISAR passes | Tubig sa mga pass ng NISAR |  |
| `spot.card.waterCount` | {k} of {n} | {k} sa {n} |  |
| `spot.card.losLabel` | Ground motion (LOS) | Galaw ng lupa (LOS) |  |
| `spot.card.losPeriod` | Total, {from} → {to} | Kabuuan, {from} → {to} |  |
| `spot.card.standingWater` | Standing water | Nakatayong tubig |  |
| `spot.card.veg` | Possible flooded vegetation | Posibleng binahang halaman |  |
| `spot.card.lastPass` | Last pass | Huling pass |  |
| `spot.card.exposureNote` | Residents & buildings inside the flooded zone (exposure, not damage). | Mga residente at gusali sa loob ng binahang sona (exposure, hindi pinsala). |  |
| `rhythm.v2.eyebrow` | FLOOD RHYTHM · 2026 WET SEASON | RITMO NG BAHA · TAG-ULAN 2026 |  |
| `rhythm.v2.headline` | {km2} km² under water on half or more of the season's passes | {km2} km² ang nasa ilalim ng tubig sa kalahati o higit pang pass |  |
| `rhythm.v2.headlineMissing` | How often each street went under water this wet season | Gaano kadalas nabaha ang bawat kalye ngayong tag-ulan |  |
| `rhythm.v2.stat.passes` | NISAR passes | Mga pass ng NISAR |  |
| `rhythm.v2.stat.period` | {from} – {to} | {from} – {to} |  |
| `rhythm.v2.stat.people` | People living there | Mga taong nakatira roon |  |
| `rhythm.v2.stat.buildingsNote` | exposure, not damage | exposure, hindi pinsala |  |
| `rhythm.v2.plainTitle` | In plain words | Sa simpleng salita |  |
| `rhythm.v2.plainBody` | NISAR passed over CAMANAVA {n} times between {from} and {to}, through clouds and rain. Light blue shows places that flooded once or twice; darker blue shows streets that flooded again and again. | Dumaan ang NISAR sa CAMANAVA nang {n} ulit mula {from} hanggang {to}, kahit may ulap at ulan. Ang mapusyaw na asul ay minsang nabaha; ang matingkad na asul ay paulit-ulit na nabaha. |  |
| `rhythm.v2.readMore` | Read more | Magbasa pa |  |
| `rhythm.v2.readLess` | Show less | Itago ang iba |  |
| `rhythm.v2.legendTitle` | Passes with water | Mga pass na may tubig |  |
| `rhythm.v2.legendMin` | 1–2 | 1–2 |  |
| `rhythm.v2.legendMax` | {n} | {n} |  |
| `rhythm.v2.legendPerm` | Permanent water | Permanenteng tubig |  |
| `season.v2.eyebrow` | SEASON · SINGLE RADAR PASS | PANAHON · ISANG RADAR PASS |  |
| `season.v2.headline` | {km2} km² of standing water on this pass | {km2} km² na nakatayong tubig sa pass na ito |  |
| `season.v2.headlineMissing` | Pass coverage on {date} | Saklaw ng pass noong {date} |  |
| `season.v2.changeSince` | Change since {date} | Pagbabago mula {date} |  |
| `season.v2.rainWindow` | Rain, {window} | Ulan, {window} |  |
| `season.v2.vegLabel` | Possible flooded vegetation | Posibleng binahang halaman |  |
| `season.v2.vegSub` | shown in amber; counted apart | nakakulay kahel; hiwalay ang bilang |  |
| `season.v2.validLabel` | Valid coverage | Wastong saklaw |  |
| `season.v2.validSub` | of study area | ng lugar ng pag-aaral |  |
| `season.v2.plainBody` | After {rain} mm of rain in the preceding week, radar mapped {km2} km² of open water on {date}. L-band radar can also bounce twice off flooded trees and crops, shown separately in amber. | Matapos ang {rain} mm ng ulan sa nakaraang linggo, naitala ng radar ang {km2} km² ng bukas na tubig noong {date}. Nakakakita rin ang L-band ng doble-talbog sa binahang puno at pananim, hiwalay sa kulay kahel. |  |
| `season.v2.plainNoRain` | On {date}, L-band radar mapped {km2} km² of open standing water across the usable scene. Possible flooded vegetation is tracked separately in amber. | Noong {date}, naitala ng L-band radar ang {km2} km² ng bukas na tubig. Hiwalay na minamarkahan sa kahel ang posibleng binahang halaman. |  |
| `season.v2.manilaLine` | {utc} UTC ({manila} Manila) · L-band HH/HV | {utc} UTC ({manila} Maynila) · L-band HH/HV |  |
| `season.v2.compareToggle` | Compare two passes (Before / After swipe) | Ihambing ang dalawang pass (Swipe Bago / Pagkatapos) |  |
| `season.v2.layerLabel` | Radar view | Tanaw ng radar |  |
| `motion.v2.eyebrow` | GROUND MOTION · LINE OF SIGHT | GALAW NG LUPA · LINE OF SIGHT |  |
| `motion.v2.headline` | Parts of CAMANAVA moved along the satellite's view between June and October | May mga bahaging gumalaw sa paningin ng satellite mula Hunyo hanggang Oktubre |  |
| `motion.v2.stat.pairs` | Interferogram pairs | Mga pares ng interferogram |  |
| `motion.v2.stat.period` | Period | Panahon |  |
| `motion.v2.stat.away` | Area moving away | Lawak na lumalayo |  |
| `motion.v2.stat.awaySub` | more than {mm} mm LOS | higit sa {mm} mm LOS |  |
| `motion.v2.stat.overlap` | Also often flooded | Madalas ding bahain |  |
| `motion.v2.stat.overlapSub` | overlapping exposure zones | magkasabay na sonang may exposure |  |
| `motion.v2.plainBody` | NISAR compares the phase of consecutive radar waves. Movement is measured along the satellite's slanted line of sight relative to a reference area on firmer ground, so moving away can include vertical sinking or sideways shift. | Inihahambing ng NISAR ang phase ng magkasunod na radar wave. Sinusukat ang galaw sa pahilis na line of sight ng satellite kumpara sa mas matatag na lupa, kaya maaaring may kasamang paglubog o pahalang na galaw. |  |
| `motion.v2.legendTitle` | Ground motion, LOS | Galaw ng lupa, LOS |  |
| `motion.v2.legendSub` | Positive = moving away from satellite | Positibo = lumalayo sa satellite |  |
| `motion.v2.legendAway` | Away (+mm) | Lumalayo (+mm) |  |
| `motion.v2.legendStable` | 0 | 0 |  |
| `motion.v2.legendToward` | Toward (−mm) | Palapit (−mm) |  |
| `motion.v2.refArea` | Reference area | Reference area |  |
| `hist.v2.eyebrow` | HISTORY · WET-SEASON RAIN SINCE 2000 | KASAYSAYAN · ULAN SA TAG-ULAN MULA 2000 |  |
| `hist.v2.headlineRank` | {year} ranks {rank} of {of} wet seasons since 2000 | Pang-{rank} ang {year} sa {of} na tag-ulan mula 2000 |  |
| `hist.v2.headline` | Wet-season rainfall in CAMANAVA since 2000 | Ulan sa tag-ulan sa CAMANAVA mula 2000 |  |
| `hist.v2.stat.sofar` | {year} so far | {year} sa ngayon |  |
| `hist.v2.stat.peak` | Wettest year | Pinakamaulang taon |  |
| `hist.v2.stat.trend` | Trend since 2000 | Trend mula 2000 |  |
| `hist.v2.chartTitle` | Wet-season rain (Jun–Nov), 2000–{year} | Ulan sa tag-ulan (Hun–Nob), 2000–{year} |  |
| `hist.v2.fullSeason` | Full season | Buong panahon |  |
| `hist.v2.wettestLegend` | Wettest: {year}, {mm} mm | Pinakamaulan: {year}, {mm} mm |  |
| `hist.v2.incompleteLegend` | {year} to {date} (incomplete) | {year} hanggang {date} (hindi pa tapos) |  |
| `hist.v2.plainBody` | Every year from 2000 is compared using the same calendar window. NASA POWER is one ~50 km reanalysis grid cell covering the whole study area, never street-level gauges, and any multi-year trend says nothing about its cause. | Bawat taon mula 2000 ay inihahambing gamit ang parehong saklaw ng kalendaryo. Ang NASA POWER ay iisang ~50 km grid cell sa buong lugar, hindi sukatan sa kalye, at walang sinasabi ang trend tungkol sa sanhi nito. |  |
| `hist.v2.mapCellTitle` | One NASA POWER grid cell (about 50 km) | Isang NASA POWER grid cell (mga 50 km) |  |
| `hist.v2.mapCellSub` | Every rainfall number here is one value for this whole cell, not street-level rain. | Bawat numero ng ulan ay iisang halaga para sa buong cell na ito, hindi ulan sa bawat kalye. |  |
| `hist.v2.mapStudy` | Study area | Lugar ng pag-aaral |  |
| `hist.v2.footerTitle` | What data exists when | Anong datos ang mayroon at kailan |  |
| `hist.v2.footerSub` | Pick a year to see what's available | Pumili ng taon upang makita ang available |  |
| `future.v2.eyebrow` | FUTURE · OUTLOOK AND CONDITIONAL SCENARIOS | HINAHARAP · OUTLOOK AT KONDISYONAL NA SENARYO |  |
| `future.v2.headline` | Seasonal rainfall outlook and conditional what-if scenarios | Pana-panahong outlook sa ulan at mga kondisyonal na senaryo |  |
| `future.v2.stat.covers` | Outlook covers | Saklaw ng outlook |  |
| `future.v2.stat.members` | {n} model runs, {res} grid | {n} model runs, {res} grid |  |
| `future.v2.stat.anom` | First month vs model normal | Unang buwan kumpara sa normal |  |
| `future.v2.stat.flood` | Flood scenario, {month} | Senaryo ng baha, {month} |  |
| `future.v2.stat.exploratory` | Exploratory | Eksploratoryo |  |
| `future.v2.pickLabel` | Choose a 12-month rainfall scenario | Pumili ng 12-buwang senaryo ng ulan |  |
| `future.v2.outlookMonths` | Outlook months | Mga buwan ng outlook |  |
| `future.v2.scenarioMonths` | Scenario months | Mga buwan ng senaryo |  |
| `future.v2.outlookMean` | Outlook model mean | Outlook model mean |  |
| `future.v2.mapLegendTitle` | Exploratory flood scenario | Eksploratoryong senaryo ng baha |  |
| `future.v2.mapLegendSub` | Where water appeared on NISAR passes after similar rain. A what-if, not a forecast of next year's floods. | Kung saan nakitang may tubig ang NISAR matapos ang katulad na ulan. Isang what-if, hindi hula ng baha sa susunod na taon. |  |
| `future.v2.footerObs` | Observed to {date} | Naobserbahan hanggang {date} |  |
| `future.v2.footerOutlook` | Outlook · {range} | Outlook · {range} |  |
| `future.v2.footerScenario` | Conditional scenario · {range} | Kondisyonal na senaryo · {range} |  |
| `time.v2.dailyRain` | Daily rain (NASA POWER) | Arawang ulan (NASA POWER) |  |
| `time.v2.nisarPass` | NISAR pass | NISAR pass |  |
| `time.v2.rain7d` | 7-day rain window | 7-araw na ulan |  |
| `time.v2.prevMonth` | Previous month | Nakaraang buwan |  |
| `time.v2.nextMonth` | Next month | Susunod na buwan |  |

## Round 2 / v6 real-data wording & IMERG updates (pending native review)

| Key | English | Current Filipino (pending native review) | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `map.tools.overlay.rhythm` | Open water outside the usual water | Bukas na tubig sa labas ng karaniwang tubig |  |
| `season.layer.flood` | Open water outside the usual water | Bukas na tubig sa labas ng karaniwang tubig |  |
| `spot.card.standingWater` | Open water outside the usual water | Bukas na tubig sa labas ng karaniwang tubig |  |
| `spot.card.imerg24h` | Rain in the 24 h before this pass: {mm} (GPM IMERG, ~11 km cell) | Ulan sa 24 oras bago ang pass na ito: {mm} (GPM IMERG, ~11 km cell) |  |
| `rhythm.v2.headline` | {km2} km² of usually-dry land had open water on half or more of NISAR's passes | {km2} km² ng karaniwang tuyong lupa ang nagkaroon ng bukas na tubig sa kalahati o higit pang pass ng NISAR |  |
| `rhythm.v2.plainBody` | NISAR passed over CAMANAVA {n} times between {from} and {to}, through clouds and rain. Light blue shows usually-dry land where open water appeared on one or two passes; darker blue shows open water outside the usual water on more passes. This layer gets smaller after heavy rain, because wet ground and rain-roughened water look brighter to the radar. | Dumaan ang NISAR sa CAMANAVA nang {n} ulit mula {from} hanggang {to}, kahit may ulap at ulan. Ang mapusyaw na asul ay karaniwang tuyong lupa na nakitaan ng bukas na tubig sa isa o dalawang pass; ang matingkad na asul ay bukas na tubig sa maraming pass. Lumiit ang layer na ito pagkatapos ng malakas na ulan dahil mas maliwanag sa radar ang basang lupa at maalon na tubig. |  |
| `rhythm.v2.limitsCallout` | Why doesn't this show flooded streets? In dense streets, radar bounces off water and walls (double-bounce) and looks bright, and NISAR passes at ~05:30 Manila time every 12 days. | Bakit hindi nito ipinapakita ang binahang kalye? Sa siksik na kalye, tumatalbog ang radar sa tubig at pader (double-bounce) kaya nagmumukhang maliwanag, at dumaraan ang NISAR bandang ~05:30 oras sa Maynila tuwing 12 araw. |  |
| `rhythm.v2.limitsBtn` | What NISAR can and can't see | Ano ang nakikita at hindi nakikita ng NISAR |  |
| `rhythm.v2.legendTitle` | Open water outside the usual water | Bukas na tubig sa labas ng karaniwang tubig |  |
| `season.v2.headline` | {km2} km² of open water outside the usual water on this pass | {km2} km² ng bukas na tubig sa labas ng karaniwang tubig sa pass na ito |  |
| `imerg.title` | Rain before this pass (NASA GPM IMERG) | Ulan bago ang pass na ito (NASA GPM IMERG) |  |
| `imerg.last24h` | Last 24 h | Huling 24 oras |  |
| `imerg.last48h` | Last 48 h | Huling 48 oras |  |
| `imerg.peak` | Peak rate | Pinakamalakas |  |
| `imerg.incomplete` | incomplete data | kulang ang datos |  |
| `imerg.hoursSince` | Last heavy rain {h} h before the pass (area mean ≥ 1.0 mm/hr) | Huling malakas na ulan {h} oras bago ang pass (mean ng lugar ≥ 1.0 mm/hr) |  |
| `imerg.noHeavyRain` | No half-hour ≥ {th} mm/hr in the 48 h before the pass | Walang kalahating oras na ≥ {th} mm/hr sa loob ng 48 oras bago ang pass |  |
| `motion.v2.unavailableIono` | Not available yet. Four months of NISAR interferograms are dominated by ionospheric noise; ground motion needs a longer record and ionosphere correction. | Hindi pa available. Ang apat na buwang interferogram ng NISAR ay pinangingibabawan ng ionospheric noise; kailangan ang mas mahabang tala at ionospheric correction. |  |
| `priority.v2.unavailable` | Not available: needs ground motion. | Hindi available: kailangan ang galaw ng lupa. |  |
| `radar.limits.title` | What NISAR can and can't see | Ano ang nakikita at hindi nakikita ng NISAR |  |
| `radar.limits.p1` | Calm open water reflects the radar away and looks dark, so open water on fishponds, lowland flats, and rivers outside the usual water stands out clearly when the surface is smooth. | Ang tahimik na bukas na tubig ay nagpapatalbog ng radar palayo kaya madilim ito sa larawan—malinaw nitong nakikita ang bukas na tubig sa mga palaisdaan, ilog, at kapatagan kapag payapa ang tubig. |  |
| `radar.limits.p2` | In a flooded street, the radar bounces off the water and then a wall straight back to the satellite (double-bounce), so the street looks bright, not dark. Narrow streets, building shadows and layover also hide the street surface. | Sa binahang kalye, tumatalbog ang radar sa tubig tapos sa pader pabalik sa satellite (double-bounce), kaya nagmumukhang maliwanag ang kalye, hindi madilim. Tinatakpan din ng makikitid na kalye, anino ng gusali, at layover ang ibabaw ng kalye. |  |
| `radar.limits.p3` | NISAR passes CAMANAVA at about 05:30 Manila time every 12 days, so floods that rise in the afternoon and drain overnight are missed. The radar does see the whole area get 'wetter' after rainy weeks: built-up and open land brighten together (Spearman ρ = 0.80 with 7-day rain, n = 11). This is general wetness, not a flood map. | Dumaraan ang NISAR sa CAMANAVA bandang ~05:30 oras sa Maynila tuwing 12 araw, kaya hindi naaabot ang biglaang pagbaha sa hapon na humuhupa bago mag-umaga. Nakikita ng radar ang pangkalahatang pagbasa ng lupa pagkatapos ng maulang linggo: sabay na umiilaw ang lungsod at bukirin (Spearman ρ = 0.80 sa 7-araw na ulan, n = 11). Pangkalahatang halumigmig ito, hindi mapa ng baha. |  |
| `radar.limits.tip` | NISAR maps open water outside the usual water and general surface wetness, not flooded city streets. | ipinapakita ng NISAR ang bukas na tubig sa labas ng karaniwang tubig at pangkalahatang basa sa ibabaw, hindi ang mga binahang kalye. |  |

## Round 3 / A8 real-data scatter & spot polish (pending native review)

| Key | English | Current Filipino (pending native review) | Corrected Filipino (draft / reviewer) |
| --- | --- | --- | --- |
| `spot.card.imerg24h` | Rain in the 24 h before the selected pass: {mm} (NASA GPM IMERG, ~11 km cell) | Ulan sa 24 oras bago ang napiling pass: {mm} (NASA GPM IMERG, ~11 km cell) |  |
| `spot.card.waterZero` | No open water outside the usual water on any of the {n} passes | Walang bukas na tubig sa labas ng karaniwang tubig sa alinman sa {n} na pass |  |
| `rhythm.v2.scatter.title` | Open water vs rain before each pass | Bukas na tubig laban sa ulan bago ang bawat pass |  |
| `rhythm.v2.scatter.xAxis` | 48 h rain before pass (mm) | Ulan sa 48 oras bago ang pass (mm) |  |
| `rhythm.v2.scatter.yAxis` | Open water (km²) | Bukas na tubig (km²) |  |
| `rhythm.v2.scatter.caption` | Each dot is one NISAR pass. Passes after heavy rain show less open water: wet ground and rain-roughened water look brighter to L-band radar. Exploratory, 11 passes. | Bawat tuldok ay isang pass ng NISAR. Mas maliit ang bukas na tubig sa mga pass pagkatapos ng malakas na ulan: mas maliwanag sa L-band radar ang basang lupa at maalon na tubig. Eksploratoryo, 11 pass. |  |
| `rhythm.v2.scatter.sources` | Sources: NASA GPM IMERG · NASA–ISRO NISAR | Pinagmulan: NASA GPM IMERG · NASA–ISRO NISAR |  |
| `rhythm.v2.scatter.aria` | Scatter plot of open water outside the usual water (km²) against 48-hour rain before each pass (mm) across {n} NISAR passes. Rain ranges from {minRain} to {maxRain} mm; open water ranges from {minWater} to {maxWater} km². | Scatter plot ng bukas na tubig sa labas ng karaniwang tubig (km²) laban sa ulan sa 48 oras bago ang bawat pass (mm) sa {n} na pass ng NISAR. Ang ulan ay mula {minRain} hanggang {maxRain} mm; ang bukas na tubig ay mula {minWater} hanggang {maxWater} km². |  |
| `rhythm.v2.scatter.showTable` | Show as table | Ipakita bilang talahanayan |  |
| `rhythm.v2.scatter.hideTable` | Hide table | Itago ang talahanayan |  |
| `rhythm.v2.scatter.colDate` | Pass date | Petsa ng pass |  |
| `rhythm.v2.scatter.colRain` | 48 h rain (mm) | Ulan sa 48 oras (mm) |  |
| `rhythm.v2.scatter.colWater` | Open water (km²) | Bukas na tubig (km²) |  |
