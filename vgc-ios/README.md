# VGC Short Links — iOS App

A native SwiftUI iPhone/iPad app for creating and managing short links on your
VGC URL Shortener instance (https://vgc.to).

## Features

- **Sign in** with the admin password (exchanges it for the server's API key via
  `POST /api/auth/login`) or paste an API key directly. The key is stored in the
  iOS Keychain and sent as the `X-API-Key` header on every request — no cookies.
- **Browse links** with server-side search, tag filtering, sorting
  (date created / clicks / last updated), and infinite-scroll pagination
  (`GET /api/urls`).
- **Create links** with optional custom alias, title, description, and tags
  (`POST /api/shorten`), then copy or share the new short URL.
- **Link detail** with total clicks, clicks today, a daily click bar chart
  (Swift Charts), recent clicks, and top referrers (`GET /api/stats/{code}`).
- **Edit links** — destination, title, description, tags, and an edit reason
  (`PUT /api/edit/{code}`) — and view the full edit history
  (`GET /api/history/{code}`).
- **Delete** (soft delete, swipe or from detail view) via `DELETE /api/delete/{code}`.
- **Settings** — server health/status, masked API key with reveal/copy,
  key regeneration (`POST /api/auth/regenerate-api-key`), and sign out.

## Requirements

- Xcode 16 or later (the project uses file-system-synchronized groups)
- iOS 17.0+ deployment target
- No third-party dependencies — just SwiftUI, Swift Charts, URLSession, and Keychain

## Getting started

1. Open `vgc-ios/VGCShortLinks.xcodeproj` in Xcode.
2. Select the **VGCShortLinks** target → *Signing & Capabilities* → choose your team
   (bundle id is `com.vancegc.VGCShortLinks`; change it if needed).
3. Build & run on a simulator or device.
4. On the sign-in screen the server defaults to `https://vgc.to`. Enter the admin
   password (or an API key) and sign in.

### Testing against a local server

App Transport Security requires HTTPS. To point the app at a plain-HTTP dev
server (e.g. `http://localhost:5000`), add an ATS exception to the target's
Info settings (`NSAppTransportSecurity` → `NSAllowsLocalNetworking`).

## Project layout

```
VGCShortLinks/
├── VGCShortLinksApp.swift       # App entry, root auth switch, tab bar
├── Models/Models.swift          # API models + tolerant UTC date parsing
├── Networking/
│   ├── APIClient.swift          # Async REST client (X-API-Key auth)
│   └── KeychainStore.swift      # Keychain wrapper for the API key
├── ViewModels/
│   ├── SessionStore.swift       # Auth state, login/logout, key storage
│   └── LinksViewModel.swift     # Pagination, search debounce, sort, delete
└── Views/
    ├── LoginView.swift
    ├── LinkListView.swift       # List + rows + sort/tag filter menu
    ├── CreateLinkView.swift
    ├── LinkDetailView.swift     # Stats, chart, recent clicks, history
    ├── EditLinkView.swift
    └── SettingsView.swift
```

## Server-side notes

- The app relies on the API key returned by `/api/auth/login`. Set a stable
  `VGC_API_KEY` environment variable on the server; otherwise the key changes on
  every server restart (and differs per gunicorn worker), which will sign the
  app out. See `AUDIT.md` at the repo root.
- All timestamps from the API are naive UTC (`datetime.utcnow().isoformat()`);
  the app parses them as UTC and displays local time.
