import Foundation

enum APIError: LocalizedError {
    case invalidBaseURL
    case unauthorized
    case server(message: String, statusCode: Int)
    case decoding(Error)
    case transport(Error)

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL:
            return "The server URL is invalid."
        case .unauthorized:
            return "Authentication failed. Check your password or API key."
        case .server(let message, _):
            return message
        case .decoding:
            return "The server returned an unexpected response."
        case .transport(let error):
            return error.localizedDescription
        }
    }
}

/// Thin async client for the VGC URL Shortener REST API.
/// Authenticates with the X-API-Key header, so no cookie/session state is needed.
final class APIClient: @unchecked Sendable {
    var baseURL: URL
    var apiKey: String?

    private let session: URLSession

    init(baseURL: URL, apiKey: String? = nil) {
        self.baseURL = baseURL
        self.apiKey = apiKey

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 20
        config.httpCookieStorage = nil
        self.session = URLSession(configuration: config)
    }

    // MARK: - Auth

    func login(password: String) async throws -> LoginResponse {
        try await request("POST", "/api/auth/login", body: LoginRequest(password: password))
    }

    func verify() async throws -> VerifyResponse {
        try await request("GET", "/api/auth/verify")
    }

    func regenerateAPIKey() async throws -> RegenerateKeyResponse {
        try await request("POST", "/api/auth/regenerate-api-key")
    }

    // MARK: - Links

    func listLinks(
        page: Int = 1,
        limit: Int = 50,
        search: String = "",
        tag: String = "",
        sort: LinkSortField = .createdAt,
        order: SortOrder = .desc
    ) async throws -> LinkListResponse {
        var query = [
            URLQueryItem(name: "page", value: String(page)),
            URLQueryItem(name: "limit", value: String(limit)),
            URLQueryItem(name: "sort", value: sort.rawValue),
            URLQueryItem(name: "order", value: order.rawValue),
        ]
        if !search.isEmpty { query.append(URLQueryItem(name: "search", value: search)) }
        if !tag.isEmpty { query.append(URLQueryItem(name: "tag", value: tag)) }
        return try await request("GET", "/api/urls", query: query)
    }

    func createLink(_ body: CreateLinkRequest) async throws -> CreateLinkResponse {
        try await request("POST", "/api/shorten", body: body)
    }

    func linkInfo(shortCode: String) async throws -> ShortLink {
        try await request("GET", "/api/info/\(shortCode)")
    }

    func editLink(shortCode: String, body: EditLinkRequest) async throws -> EditLinkResponse {
        try await request("PUT", "/api/edit/\(shortCode)", body: body)
    }

    func deleteLink(shortCode: String) async throws -> SimpleResponse {
        try await request("DELETE", "/api/delete/\(shortCode)")
    }

    func restoreLink(shortCode: String) async throws -> SimpleResponse {
        try await request("POST", "/api/restore/\(shortCode)")
    }

    func stats(shortCode: String) async throws -> StatsResponse {
        try await request("GET", "/api/stats/\(shortCode)")
    }

    func history(shortCode: String) async throws -> HistoryResponse {
        try await request("GET", "/api/history/\(shortCode)")
    }

    func tags() async throws -> TagsResponse {
        try await request("GET", "/api/tags")
    }

    func health() async throws -> HealthResponse {
        try await request("GET", "/api/health")
    }

    // MARK: - Plumbing

    private struct EmptyBody: Encodable {}

    private func request<T: Decodable>(
        _ method: String,
        _ path: String,
        query: [URLQueryItem] = []
    ) async throws -> T {
        try await request(method, path, query: query, body: Optional<EmptyBody>.none)
    }

    private func request<T: Decodable, B: Encodable>(
        _ method: String,
        _ path: String,
        query: [URLQueryItem] = [],
        body: B?
    ) async throws -> T {
        guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
            throw APIError.invalidBaseURL
        }
        components.path = path
        if !query.isEmpty { components.queryItems = query }
        guard let url = components.url else { throw APIError.invalidBaseURL }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let apiKey, !apiKey.isEmpty {
            request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        }
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = try APIDate.encoder.encode(body)
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.transport(error)
        }

        guard let http = response as? HTTPURLResponse else {
            throw APIError.server(message: "Invalid server response", statusCode: 0)
        }

        guard (200..<300).contains(http.statusCode) else {
            if http.statusCode == 401 { throw APIError.unauthorized }
            let message = (try? APIDate.decoder.decode(APIErrorBody.self, from: data))
                .flatMap { $0.error ?? $0.message }
                ?? "Request failed (HTTP \(http.statusCode))"
            throw APIError.server(message: message, statusCode: http.statusCode)
        }

        do {
            return try APIDate.decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }
}
