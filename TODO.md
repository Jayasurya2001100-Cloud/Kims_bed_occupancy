# TODO - Dynamic Registration & Bed Allocation Platform

## Plan (high level)
1. Verify existing backend/ and frontend/ capabilities.
2. Add missing backend endpoints / upgrade existing ones to meet dynamic requirements:
   - payer_channel-aware forecasting integration (remove mock payer forecast; segment by payer_channel from model/feature).
   - payer eligibility validation.
   - dynamic inventory update + bed allocation monitor state.
   - bed-status endpoint to return cleaning/maintenance/reserved/transfers and predicted occupancy impact.
   - alerts endpoint to be fully threshold/API-driven (no hardcoded ICU/overall/ED limits).
   - expose configuration metadata needed by UI (dept/specialty/payer channels already present; ensure no hardcoding).
3. Update backend bed recommendation engine:
   - apply hospital business rules from /api/config/business-rules.
   - ensure rules are data-driven (no hardcoded department lists, specialty lists, thresholds).
   - exclude maintenance/cleaning/reserved beds.
   - include alternatives and reasoning.
4. Update frontend to consume new APIs and render:
   - Registration (/registration)
   - Recommendations (/recommendations) if required as separate screen (or fold into registration UI)
   - Payer intelligence (/payer-intelligence)
   - Occupancy alerts (/occupancy-alerts)
   - Bed allocation monitor (/bed-allocation-monitor) with real-time updates (SSE/polling)
5. Generate TS interfaces, hooks, services, loading/error/skeleton components as needed (preserving existing design patterns).
6. Run frontend build and backend tests.


## Step tracking
- [x] Step 1: Repo understanding completed (read backend + key frontend files).

- [ ] Step 2: Backend analysis for current gaps vs required endpoints.
- [ ] Step 3: Draft backend changes (endpoints + services + DTOs + validation schemas).
- [ ] Step 4: Draft frontend changes (screens/components/hooks/services).
- [ ] Step 5: Implement backend changes.
- [ ] Step 6: Implement frontend changes.
- [ ] Step 7: Testing (backend tests + frontend build/run).


## Progress / status after latest code inspection
- Backend code compiles (Python `py_compile` pass on `HSI-backend/main.py`).
- Frontend build/test could not be executed due to local Node/npm installation error:
  - `Error: Cannot find module ... pm-prefix.js` (npm is broken in this environment).
- README/verification checklist remains largely unchecked; system cannot be fully validated end-to-end until frontend tooling works.

