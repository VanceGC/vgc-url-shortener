import Foundation
import SwiftUI

/// Owns authentication state and the shared API client.
///
/// Login exchanges the admin password for the server's API key via
/// POST /api/auth/login; the key is stored in the Keychain and sent as
/// the X-API-Key header on every subsequent request, so the app never
/// depends on session cookies.
@MainActor
final class SessionStore: ObservableObject {
    static let defaultServer = "https://vgc.to"
    private static let apiKeyAccount = "api-key"
    private static let serverDefaultsKey = "serverURL"

    @Published var isAuthenticated = false
    @Published var serverURLString: String {
        didSet { UserDefaults.standard.set(serverURLString, forKey: Self.serverDefaultsKey) }
    }

    let client: APIClient

    var apiKey: String? { client.apiKey }

    init() {
        let stored = UserDefaults.standard.string(forKey: Self.serverDefaultsKey)
        let server = (stored?.isEmpty == false ? stored! : Self.defaultServer)
        self.serverURLString = server

        let url = URL(string: server) ?? URL(string: Self.defaultServer)!
        self.client = APIClient(baseURL: url, apiKey: KeychainStore.load(Self.apiKeyAccount))
        self.isAuthenticated = client.apiKey?.isEmpty == false
    }

    var baseURL: URL {
        client.baseURL
    }

    private func applyServer(_ urlString: String) throws {
        let trimmed = urlString.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let url = URL(string: trimmed), url.scheme != nil, url.host != nil else {
            throw APIError.invalidBaseURL
        }
        serverURLString = trimmed
        client.baseURL = url
    }

    /// Exchange the admin password for the API key.
    func login(server: String, password: String) async throws {
        try applyServer(server)
        client.apiKey = nil
        let response = try await client.login(password: password)
        guard response.success == true, let key = response.apiKey, !key.isEmpty else {
            throw APIError.server(message: response.message ?? "Login failed", statusCode: 200)
        }
        setAPIKey(key)
    }

    /// Sign in directly with an existing API key (verified against /api/auth/verify).
    func login(server: String, apiKey: String) async throws {
        try applyServer(server)
        let key = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        client.apiKey = key
        do {
            _ = try await client.verify()
        } catch {
            client.apiKey = nil
            throw error
        }
        setAPIKey(key)
    }

    func regenerateAPIKey() async throws {
        let response = try await client.regenerateAPIKey()
        setAPIKey(response.newApiKey)
    }

    func logout() {
        KeychainStore.delete(Self.apiKeyAccount)
        client.apiKey = nil
        isAuthenticated = false
    }

    private func setAPIKey(_ key: String) {
        KeychainStore.save(key, for: Self.apiKeyAccount)
        client.apiKey = key
        isAuthenticated = true
    }
}
