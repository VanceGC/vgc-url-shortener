import SwiftUI
import UIKit

struct SettingsView: View {
    @EnvironmentObject private var session: SessionStore

    @State private var health: HealthResponse?
    @State private var showAPIKey = false
    @State private var showingRegenerateConfirm = false
    @State private var showingLogoutConfirm = false
    @State private var errorMessage: String?
    @State private var infoMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Server") {
                    LabeledContent("URL", value: session.serverURLString)
                    if let health {
                        LabeledContent("Status") {
                            Label(
                                health.status.capitalized,
                                systemImage: health.status == "healthy"
                                    ? "checkmark.circle.fill" : "exclamationmark.triangle.fill"
                            )
                            .foregroundStyle(health.status == "healthy" ? .green : .orange)
                        }
                        if let version = health.version {
                            LabeledContent("API Version", value: version)
                        }
                        if let totalUrls = health.totalUrls {
                            LabeledContent("Total Links", value: "\(totalUrls)")
                        }
                        if let totalClicks = health.totalClicks {
                            LabeledContent("Total Clicks", value: "\(totalClicks)")
                        }
                    } else {
                        LabeledContent("Status") { ProgressView() }
                    }
                }

                Section {
                    LabeledContent("API Key") {
                        Text(showAPIKey ? (session.apiKey ?? "—") : maskedKey)
                            .font(.callout.monospaced())
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }
                    Button(showAPIKey ? "Hide Key" : "Reveal Key") {
                        showAPIKey.toggle()
                    }
                    Button("Copy Key") {
                        UIPasteboard.general.string = session.apiKey
                        infoMessage = "API key copied to clipboard."
                    }
                    Button("Regenerate Key", role: .destructive) {
                        showingRegenerateConfirm = true
                    }
                } header: {
                    Text("API Access")
                } footer: {
                    Text("The key is stored in the iOS Keychain and sent as the X-API-Key header. Regenerating invalidates the key everywhere else it's used (scripts, N8N, etc.).")
                }

                Section {
                    Button("Sign Out", role: .destructive) {
                        showingLogoutConfirm = true
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .navigationTitle("Settings")
            .task { await loadHealth() }
            .refreshable { await loadHealth() }
            .confirmationDialog(
                "Regenerate API key?",
                isPresented: $showingRegenerateConfirm,
                titleVisibility: .visible
            ) {
                Button("Regenerate", role: .destructive) { regenerate() }
            } message: {
                Text("Every other client using the current key will stop working.")
            }
            .confirmationDialog(
                "Sign out?",
                isPresented: $showingLogoutConfirm,
                titleVisibility: .visible
            ) {
                Button("Sign Out", role: .destructive) { session.logout() }
            }
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
            .alert(
                "Done",
                isPresented: Binding(
                    get: { infoMessage != nil },
                    set: { if !$0 { infoMessage = nil } }
                )
            ) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(infoMessage ?? "")
            }
        }
    }

    private var maskedKey: String {
        guard let key = session.apiKey, key.count > 8 else { return "••••••••" }
        return "\(key.prefix(6))••••••••\(key.suffix(4))"
    }

    private func loadHealth() async {
        do {
            health = try await session.client.health()
        } catch {
            if health == nil { errorMessage = error.localizedDescription }
        }
    }

    private func regenerate() {
        Task {
            do {
                try await session.regenerateAPIKey()
                infoMessage = "API key regenerated and saved."
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}

#Preview {
    SettingsView().environmentObject(SessionStore())
}
