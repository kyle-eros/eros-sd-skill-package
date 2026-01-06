# Send Types Reference

**Version**: 5.0.0 | **Total Types**: 22

---

## Revenue Types (9)

| Key | Page Type | Daily Max | Weekly Max | Min Gap | Requires Media | Requires Price |
|-----|-----------|-----------|------------|---------|----------------|----------------|
| `ppv_unlock` | both | 4 | - | 2h | YES | YES |
| `ppv_wall` | FREE only | 3 | - | 3h | YES | YES |
| `tip_goal` | PAID only | 2 | - | 4h | NO | YES |
| `bundle` | both | 1 | - | 3h | YES | YES |
| `flash_bundle` | both | 1 | - | 6h | YES | YES |
| `vip_program` | both | 1 | 1 | 24h | NO | NO |
| `game_post` | both | 1 | - | 4h | NO | NO |
| `snapchat_bundle` | both | 1 | 1 | 24h | YES | NO |
| `first_to_tip` | both | 1 | - | 6h | NO | NO |

### Revenue Type Details

- **ppv_unlock**: Primary monetization via mass message PPV
- **ppv_wall**: FREE page only - wall post with locked content
- **tip_goal**: PAID page only - tip meter toward goal
- **bundle**: Multi-content package at discount
- **flash_bundle**: Time-limited bundle with urgency
- **vip_program**: Upsell to premium tier (weekly max: 1)
- **game_post**: Interactive engagement with prize
- **snapchat_bundle**: Cross-platform upsell (weekly max: 1)
- **first_to_tip**: Gamified tip competition

---

## Engagement Types (9)

| Key | Page Type | Daily Max | Min Gap | Requires Media |
|-----|-----------|-----------|---------|----------------|
| `link_drop` | both | 2 | 2h | NO |
| `wall_link_drop` | both | 2 | 3h | YES |
| `bump_normal` | both | 3 | 1h | NO |
| `bump_descriptive` | both | 2 | 2h | NO |
| `bump_text_only` | both | 2 | 2h | NO |
| `bump_flyer` | both | 2 | 4h | YES |
| `dm_farm` | both | 2 | 4h | NO |
| `like_farm` | both | 1 | 24h | NO |
| `live_promo` | both | 2 | 2h | YES |

### Engagement Type Details

- **link_drop**: Cross-platform link (Instagram, TikTok, etc.)
- **wall_link_drop**: Wall post with external link
- **bump_normal**: Re-engage conversation
- **bump_descriptive**: Story-style bump with detail
- **bump_text_only**: Pure text bump (no media)
- **bump_flyer**: Visual bump with promotional graphic
- **dm_farm**: Solicit DM responses for engagement
- **like_farm**: Request post likes (once per day)
- **live_promo**: Promote upcoming live session

---

## Retention Types (4)

| Key | Page Type | Daily Max | Min Gap | Notes |
|-----|-----------|-----------|---------|-------|
| `renew_on_post` | PAID only | 2 | 12h | Subscription renewal via post |
| `renew_on_message` | PAID only | 1 | 24h | Subscription renewal via DM |
| `ppv_followup` | both | 5 | 1h | Auto-generated 15-45min after parent PPV |
| `expired_winback` | PAID only | 1 | 24h | Win back expired subscribers |

### Retention Type Details

- **renew_on_post**: Remind expiring subscribers via wall
- **renew_on_message**: Personal renewal reminder via DM
- **ppv_followup**: Re-target non-purchasers (auto-generated)
- **expired_winback**: Re-engage lapsed subscribers

---

## Page Type Restrictions

### FREE Pages Cannot Use:
- `tip_goal` (requires subscription pricing)
- `renew_on_post` (no subscription to renew)
- `renew_on_message` (no subscription to renew)
- `expired_winback` (no expiring subscriptions)

### PAID Pages Cannot Use:
- `ppv_wall` (wall posts are free for subscribers)

---

## Flyer Requirements

The following send types MUST have `flyer_required = 1`:

```
ppv_unlock, ppv_wall, bundle, flash_bundle,
vip_program, snapchat_bundle, first_to_tip,
bump_flyer, live_promo
```

---

## Category Classification

| Category | Types | Primary Purpose |
|----------|-------|-----------------|
| REVENUE | ppv_unlock, ppv_wall, tip_goal, bundle, flash_bundle, vip_program, game_post, snapchat_bundle, first_to_tip | Direct monetization |
| ENGAGEMENT | link_drop, wall_link_drop, bump_normal, bump_descriptive, bump_text_only, bump_flyer, dm_farm, like_farm, live_promo | Audience interaction |
| RETENTION | renew_on_post, renew_on_message, ppv_followup, expired_winback | Subscriber retention |

---

## Daily Volume Guidance

| Category | Typical Range | Peak Days |
|----------|---------------|-----------|
| Revenue | 4-9 per day | Weekends, Paydays |
| Engagement | 4-8 per day | Weekdays |
| Retention | 2-4 per day | Renewal windows |

---

*End of Send Types Reference*
