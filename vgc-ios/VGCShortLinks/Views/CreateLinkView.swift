import SwiftUI
import UIKit

struct CreateLinkView: View {
    @EnvironmentObject private var session: SessionStore
    @Environment(\.dismiss) private var dismiss

    var onCreated: (ShortLink) -> Void

    @State private var urlText = ""
    @State private var customAlias = ""
    @State private var title = ""
    @State private var descriptionText = ""
    @State private var tagsText = ""
    @State private var isWorking = false
    @State private var errorMessage: String?
    @State private var createdURL: String?

    var body: some View {
        NavigationStack {
            Form {
                if let createdURL {
                    successSection(createdURL)
                } else {
                    formSections
                }
            }
            .navigationTitle(createdURL == nil ? "New Link" : "Link Created")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(createdURL == nil ? "Cancel" : "Done") { dismiss() }
                }
                if createdURL == nil {
                    ToolbarItem(placement: .confirmationAction) {
                        if isWorking {
                            ProgressView()
                        } else {
                            Button("Create") { create() }
                                .disabled(urlText.trimmingCharacters(in: .whitespaces).isEmpty)
                        }
                    }
                }
            }
            .interactiveDismissDisabled(isWorking)
        }
    }

    @ViewBuilder
    private var formSections: some View {
        Section("Destination") {
            TextField("https://example.com/long/path", text: $urlText, axis: .vertical)
                .keyboardType(.URL)
                .textContentType(.URL)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
                .lineLimit(1...4)
        }

        Section {
            TextField("Custom alias (optional)", text: $customAlias)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
        } header: {
            Text("Short Code")
        } footer: {
            Text("3–10 letters or digits. Leave blank for a random code.")
        }

        Section("Details (optional)") {
            TextField("Title", text: $title)
            TextField("Description", text: $descriptionText, axis: .vertical)
                .lineLimit(1...3)
            TextField("Tags (comma-separated)", text: $tagsText)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
        }

        if let errorMessage {
            Section {
                Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                    .foregroundStyle(.red)
                    .font(.callout)
            }
        }
    }

    private func successSection(_ shortURL: String) -> some View {
        Section {
            VStack(spacing: 12) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 44))
                    .foregroundStyle(.green)
                Text(shortURL)
                    .font(.title3.monospaced())
                    .textSelection(.enabled)
                HStack(spacing: 16) {
                    Button {
                        UIPasteboard.general.string = shortURL
                    } label: {
                        Label("Copy", systemImage: "doc.on.doc")
                    }
                    .buttonStyle(.bordered)

                    if let url = URL(string: shortURL) {
                        ShareLink(item: url) {
                            Label("Share", systemImage: "square.and.arrow.up")
                        }
                        .buttonStyle(.bordered)
                    }
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
        }
    }

    private func create() {
        isWorking = true
        errorMessage = nil

        let tags = tagsText
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        let alias = customAlias.trimmingCharacters(in: .whitespaces)
        let request = CreateLinkRequest(
            url: urlText.trimmingCharacters(in: .whitespacesAndNewlines),
            customAlias: alias.isEmpty ? nil : alias,
            title: title.isEmpty ? nil : title,
            description: descriptionText.isEmpty ? nil : descriptionText,
            tags: tags.isEmpty ? nil : tags
        )

        Task {
            defer { isWorking = false }
            do {
                let response = try await session.client.createLink(request)
                createdURL = response.shortUrl
                // Fetch the full record so the list row has id/click data.
                if let link = try? await session.client.linkInfo(shortCode: response.shortCode) {
                    onCreated(link)
                }
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}
