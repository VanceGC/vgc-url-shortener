import SwiftUI

struct EditLinkView: View {
    @EnvironmentObject private var session: SessionStore
    @Environment(\.dismiss) private var dismiss

    let link: ShortLink
    var onSave: (ShortLink) -> Void

    @State private var urlText: String
    @State private var title: String
    @State private var descriptionText: String
    @State private var tagsText: String
    @State private var reason = ""
    @State private var isWorking = false
    @State private var errorMessage: String?

    init(link: ShortLink, onSave: @escaping (ShortLink) -> Void) {
        self.link = link
        self.onSave = onSave
        _urlText = State(initialValue: link.originalUrl)
        _title = State(initialValue: link.title ?? "")
        _descriptionText = State(initialValue: link.description ?? "")
        _tagsText = State(initialValue: link.tags.joined(separator: ", "))
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Destination") {
                    TextField("https://example.com", text: $urlText, axis: .vertical)
                        .keyboardType(.URL)
                        .textContentType(.URL)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                        .lineLimit(1...4)
                }

                Section("Details") {
                    TextField("Title", text: $title)
                    TextField("Description", text: $descriptionText, axis: .vertical)
                        .lineLimit(1...3)
                    TextField("Tags (comma-separated)", text: $tagsText)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                }

                Section {
                    TextField("Reason for change (optional)", text: $reason)
                } footer: {
                    Text("Recorded in the link's edit history.")
                }

                if let errorMessage {
                    Section {
                        Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.red)
                            .font(.callout)
                    }
                }
            }
            .navigationTitle("Edit \(link.shortCode)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if isWorking {
                        ProgressView()
                    } else {
                        Button("Save") { save() }
                            .disabled(urlText.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                }
            }
            .interactiveDismissDisabled(isWorking)
        }
    }

    private func save() {
        isWorking = true
        errorMessage = nil

        let tags = tagsText
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        let request = EditLinkRequest(
            url: urlText.trimmingCharacters(in: .whitespacesAndNewlines),
            title: title.isEmpty ? nil : title,
            description: descriptionText.isEmpty ? nil : descriptionText,
            tags: tags,
            reason: reason.isEmpty ? nil : reason
        )

        Task {
            defer { isWorking = false }
            do {
                let response = try await session.client.editLink(shortCode: link.shortCode, body: request)
                onSave(response.url)
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}
