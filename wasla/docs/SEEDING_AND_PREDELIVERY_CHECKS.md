# Seed Data & Pre-delivery Checks (Wasla v0.1)

## 1) Demo Seed (Products + Images)
### From Admin QA Dashboard
1. Go to `/admin/qa-dashboard/`
2. Click **Seed Demo Products** for the target store
3. Then click **Build/Update Index**
4. Try Visual Search at `/dashboard/ai/visual-search`

### From CLI
```bash
python manage.py seed_demo_products --store-id 1 --count 24 --reset --with-inventory --white-bg-ratio 0.7
python manage.py ai_kpi_visual_search --store-id 1 --samples 20 --top-n 12
```

## 2) Pre-delivery manual checklist (the checks we agreed on)
- [ ] Compare project implementation against the requirement worksheet (prototype scenarios + AI functionalities)
- [ ] Verify registration + onboarding flow matches screenshots (1→13)
- [ ] Verify wizard progress updates `setup_step` and persists in DB
- [ ] Verify tenant ownership and that all merchant data is store-scoped
- [ ] Verify Visual Search:
  - [ ] Index builds successfully
  - [ ] Search returns results
  - [ ] Filters work (price/color/brightness/white_background)
  - [ ] No server errors
- [ ] Verify email (SMTP): registration OTP / email flows
- [ ] Verify Admin QA dashboard works

## 3) Notes
- If you enable CLIP embeddings, install `torch` and `transformers` then set env vars:
  - `AI_USE_CLIP_EMBEDDINGS=1`
  - `AI_USE_CLIP_CATEGORIES=1`
