import SwiftUI
import UIKit
import Charts

struct LinkDetailView: View {
    @EnvironmentObject private var session: SessionStore
    @Environment(\.dismiss) private var dismiss

    @State var link: ShortLink
    var onUpdate: (ShortLink) -> Void
    var onDelete: (ShortLink) -> Void

    @State private var stats: StatsResponse?
    @State private var showingEdit = false
    @State private var showingDeleteConfirm = false
    @State private var errorMessage: String?

    private var shortURL: URL { link.shortURL(base: session.baseURL) }

    var body: some View {
        List {
            headerSection
            detailsSection
            statsSection
            recentActivitySection
            referrersSection

            Section {
                NavigationLink {
                    EditHistoryView(shortCode: link.shortCode)
                        .environmentObject(session)
                } label: {
                    Label("Edit History", systemImage: "clock.arrow.circlepath")
                }
            }

            Section {
                Button(role: .destructive) {
                    showingDeleteConfirm = true
                } label: {
                    Label("Delete Link", systemImage: "trash")
                        .frame(maxWidth: .infinity)
                }
            }
        }
        .navigationTitle(link.shortCode)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button("Edit") { showingEdit = true }
            }
        }
        .sheet(isPresented: $showingEdit) {
            EditLinkView(link: link) { updated in
                link = updated
                onUpdate(updated)
                Task { await loadStats() }
            }
            .environmentObject(session)
        }
        .confirmationDialog(
            "Delete this link?",
            isPresented: $showingDeleteConfirm,
            titleVisibility: .visible
        ) {
            Button("Delete \(link.shortCode)", role: .destructive) { deleteLink() }
        } message: {
            Text("The link is soft-deleted on the server and can be restored via the API.")
        }
        .task { await loadStats() }
        .refreshable { await loadStats() }
        .alert(
            "Error",
            isPresented: Binding(
                get: { errorMessage != nil },
                set: { if !$0 { errorMessage = nil } }
            )
        ) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(errorMessage ?? "")
        }
    }

    // MARK: - Sections

    private var headerSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 10) {
                Text(link.displayTitle)
                    .font(.headline)
                Text(shortURL.absoluteString)
                    .font(.callout.monospaced())
                    .foregroundStyle(.tint)
                    .textSelection(.enabled)

                HStack(spacing: 12) {
                    Button {
                        UIPasteboard.general.string = shortURL.absoluteString
                    } label: {
                        Label("Copy", systemImage: "doc.on.doc")
                    }
                    ShareLink(item: shortURL) {
                        Label("Share", systemImage: "square.and.arrow.up")
                    }
                    if let destination = URL(string: link.originalUrl) {
                        Link(destination: destination) {
                            Label("Open", systemImage: "safari")
                        }
                    }
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
            .padding(.vertical, 4)
        }
    }

    private var detailsSection: some View {
        Section("Details") {
            LabeledContent("Destination") {
                Text(link.originalUrl)
                    .lineLimit(3)
                    .multilineTextAlignment(.trailing)
                    .textSelection(.enabled)
            }
            if let description = link.description, !description.isEmpty {
                LabeledContent("Description", value: description)
            }
            if !link.tags.isEmpty {
                LabeledContent("Tags", value: link.tags.joined(separator: ", "))
            }
            if let created = link.createdAt {
                LabeledContent("Created", value: created.formatted(date: .abbreviated, time: .shortened))
            }
            if let updated = link.updatedAt {
                LabeledContent("Updated", value: updated.formatted(date: .abbreviated, time: .shortened))
            }
            if link.customAlias == true {
                LabeledContent("Alias", value: "Custom")
            }
        }
    }

    @ViewBuilder
    private var statsSection: some View {
        Section("Statistics") {
            HStack {
                statTile("Total Clicks", value: "\(stats?.totalClicks ?? link.clicks)")
                Divider()
                statTile("Today", value: "\(todayClicks)")
            }
            .frame(maxWidth: .infinity)

            if let last = link.lastClicked ?? stats?.urlInfo.lastClicked {
                LabeledContent("Last Clicked", value: last.formatted(date: .abbreviated, time: .shortened))
            }

            if let daily = stats?.dailyStats, !daily.isEmpty {
                Chart(daily) { stat in
                    BarMark(
                        x: .value("Date", stat.date),
                        y: .value("Clicks", stat.clicks)
                    )
                    .foregroundStyle(.tint)
                }
                .frame(height: 160)
                .padding(.vertical, 4)
            } else if stats != nil {
                Text("No click data yet today.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
            } else {
                ProgressView()
                    .frame(maxWidth: .infinity)
            }
        }
    }

    @ViewBuilder
    private var recentActivitySection: some View {
        if let clicks = stats?.recentClicks, !clicks.isEmpty {
            Section("Recent Clicks") {
                ForEach(clicks.prefix(10)) { click in
                    VStack(alignment: .leading, spacing: 2) {
                        if let at = click.clickedAt {
                            Text(at.formatted(date: .abbreviated, time: .shortened))
                                .font(.callout)
                        }
                        HStack(spacing: 8) {
                            if let ip = click.ipAddress {
                                Text(ip)
                            }
                            if let referer = click.referer, !referer.isEmpty {
                                Text("via \(referer)").lineLimit(1)
                            }
                        }
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var referrersSection: some View {
        if let referrers = stats?.topReferrers, !referrers.isEmpty {
            Section("Top Referrers") {
                ForEach(referrers) { referrer in
                    LabeledContent(referrer.referer) {
                        Text("\(referrer.count)")
                    }
                    .lineLimit(1)
                }
            }
        }
    }

    /// Clicks today: from the list payload if present, otherwise from today's
    /// daily-stat row returned by /api/stats.
    private var todayClicks: Int {
        if let today = link.clicksToday { return today }
        if let daily = stats?.dailyStats.last { return daily.clicks }
        return 0
    }

    private func statTile(_ label: String, value: String) -> some View {
        VStack(spacing: 4) {
            Text(value).font(.title2.bold())
            Text(label).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Actions

    private func loadStats() async {
        do {
            let response = try await session.client.stats(shortCode: link.shortCode)
            stats = response
            link = response.urlInfo
        } catch {
            if stats == nil { errorMessage = error.localizedDescription }
        }
    }

    private func deleteLink() {
        Task {
            do {
                _ = try await session.client.deleteLink(shortCode: link.shortCode)
                onDelete(link)
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}

// MARK: - Edit history

struct EditHistoryView: View {
    @EnvironmentObject private var session: SessionStore
    let shortCode: String

    @State private var records: [EditRecord] = []
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        List {
            if isLoading {
                ProgressView().frame(maxWidth: .infinity)
            } else if let errorMessage {
                Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.red)
            } else if records.isEmpty {
                ContentUnavailableView(
                    "No Edits",
                    systemImage: "clock.arrow.circlepath",
                    description: Text("This link hasn't been edited yet.")
                )
            } else {
                ForEach(records) { record in
                    VStack(alignment: .leading, spacing: 6) {
                        if let at = record.editedAt {
                            Text(at.formatted(date: .abbreviated, time: .shortened))
                                .font(.subheadline.bold())
                        }
                        if record.oldUrl != record.newUrl {
                            Text("From: \(record.oldUrl)")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                            Text("To: \(record.newUrl)")
                                .font(.caption)
                                .lineLimit(2)
                        }
                        if let reason = record.editReason, !reason.isEmpty {
                            Text("Reason: \(reason)")
                                .font(.caption)
                                .italic()
                        }
                    }
                    .padding(.vertical, 2)
                }
            }
        }
        .navigationTitle("Edit History")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            do {
                records = try await session.client.history(shortCode: shortCode).editHistory
            } catch {
                errorMessage = error.localizedDescription
            }
            isLoading = false
        }
    }
}
