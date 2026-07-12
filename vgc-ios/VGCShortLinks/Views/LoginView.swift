import SwiftUI

struct LoginView: View {
    private enum Mode: String, CaseIterable, Identifiable {
        case password = "Password"
        case apiKey = "API Key"
        var id: String { rawValue }
    }

    @EnvironmentObject private var session: SessionStore

    @State private var server = ""
    @State private var mode: Mode = .password
    @State private var password = ""
    @State private var apiKey = ""
    @State private var isWorking = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(spacing: 8) {
                        Image(systemName: "link.circle.fill")
                            .font(.system(size: 56))
                            .foregroundStyle(.tint)
                        Text("VGC Short Links")
                            .font(.title2.bold())
                        Text("Manage your vgc.to short links")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .listRowBackground(Color.clear)
                }

                Section("Server") {
                    TextField("https://vgc.to", text: $server)
                        .keyboardType(.URL)
                        .textContentType(.URL)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                }

                Section("Sign In") {
                    Picker("Method", selection: $mode) {
                        ForEach(Mode.allCases) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)

                    switch mode {
                    case .password:
                        SecureField("Admin password", text: $password)
                            .textContentType(.password)
                    case .apiKey:
                        SecureField("vgc_…", text: $apiKey)
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.never)
                    }
                }

                if let errorMessage {
                    Section {
                        Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.red)
                            .font(.callout)
                    }
                }

                Section {
                    Button(action: signIn) {
                        if isWorking {
                            ProgressView().frame(maxWidth: .infinity)
                        } else {
                            Text("Sign In")
                                .frame(maxWidth: .infinity)
                                .fontWeight(.semibold)
                        }
                    }
                    .disabled(isWorking || credential.isEmpty)
                }
            }
            .navigationTitle("Sign In")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                if server.isEmpty { server = session.serverURLString }
            }
        }
    }

    private var credential: String {
        mode == .password ? password : apiKey
    }

    private func signIn() {
        isWorking = true
        errorMessage = nil
        Task {
            defer { isWorking = false }
            do {
                switch mode {
                case .password:
                    try await session.login(server: server, password: password)
                case .apiKey:
                    try await session.login(server: server, apiKey: apiKey)
                }
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}

#Preview {
    LoginView().environmentObject(SessionStore())
}
