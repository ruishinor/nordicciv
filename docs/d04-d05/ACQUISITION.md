# Bounded N50 acquisition

`tools/d04_acquire_n50.py` uses the published Geonorge [download API](https://nedlasting.geonorge.no/help/documentation), selects candidate municipalities by overlap with the existing pilot and a 2 km buffer, requests only municipal FileGDB files, and checks the returned dataset UUID and area before download. It caps individual archives at 100 MiB, total compressed bytes at 400 MiB per pilot, and expanded archive size at 600 MiB each. It requires Fiona for local FileGDB inspection; no new runtime dependency. Actual schemas are inspected rather than assumed; only explicit water area/line classes are selected. It reuses d04_water_prep.clip and records input/output hashes and sizes. No national download.

Run: python tools/d04_acquire_n50.py --region aurland

The branch-only acquisition workflow runs both Norwegian pilots independently and uploads clipped geometry and acquisition reports. Raw archives stay outside Git. Existing rendered municipal bboxes are conservative candidates, not survey-grade coverage boundaries. Output may be partial even when a job succeeds; inspect errors, input municipality list, schema and source coverage before acceptance. No data result is claimed before artifact/log review. Denmark remains blocked on the primary provider migration/authentication; isolated Overture fallback remains available via the prepared SQL, but is not automatically published.

D03R and runtime remain untouched.
