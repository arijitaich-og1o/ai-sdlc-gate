# Project Charter — Loyalty Points Revamp

**Status:** Approved
**Prepared by:** Growth squad
**Date:** 2026-08-30

## Background

Our loyalty programme has not changed since 2019 and customers say it is confusing. Marketing wants a revamp
before the festive season and leadership has agreed. We will modernise everything related to loyalty, points,
tiers, partner rewards, the mobile wallet integration and anything else the customer touches around rewards.

## Goals

- Make the programme better and more engaging.
- Increase customer happiness.
- Be ready for the festive season.

## Scope

Everything related to the loyalty experience across web, app, POS and partner channels.

## Approach

We will rebuild the points ledger as a new microservice, migrate 48 million customer accounts from the legacy
Oracle system, and launch the new tier model at the same time. The mobile team will ship the wallet integration
in parallel and we will integrate all streams in the final week.

To speed up the migration, the data team will export the full customer table (name, email, phone, date of
birth, Aadhaar number for KYC'd members and purchase history) to a shared S3 bucket that all squads can read.

## Timeline

| Milestone | Date |
|---|---|
| Kick-off | 2026-09-01 |
| Ledger service complete | 2026-09-25 |
| Migration of 48M accounts | 2026-10-01 |
| Wallet integration complete | 2026-10-01 |
| Launch (announced to press and partners) | 2026-10-05 |

The launch date has been communicated externally and cannot move.

## Team

The Growth squad, the Data team and the Mobile team will work on this. Decisions will be taken in the weekly sync.

## Budget

Estimated at 6 engineers for about a month.

## Access details for the squads

Legacy Oracle read replica: `oracle-legacy.internal:1521`, user `loyalty_ro`, password `Ly@lty#2019ro`.
Partner rewards API sandbox key: `prt-sbx-7f3a9c1e2b4d5f6a7b8c9d0e1f2a3b4c`.

## Open questions

- Which partner rewards will be supported at launch?
- Do we need legal sign-off for the new terms?
