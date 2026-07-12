import Foundation

// MARK: - Core entities

struct ShortLink: Codable, Identifiable, Hashable {
    let id: Int
    let shortCode: String
    var originalUrl: String
    var title: String?
    var description: String?
    let createdAt: Date?
    let updatedAt: Date?
    let clicks: Int
    let customAlias: Bool?
    let expiresAt: Date?
    let isActive: Bool?
    var tags: [String]
    // Only present when the API includes stats
    let clicksToday: Int?
    let lastClicked: Date?

    var displayTitle: String {
        if let title, !title.isEmpty { return title }
        if let host = URL(string: originalUrl)?.host { return host }
        return originalUrl
    }

    func shortURL(base: URL) -> URL {
        base.appendingPathComponent(shortCode)
    }
}

struct ClickRecord: Codable, Identifiable, Hashable {
    let id: Int
    let urlId: Int
    let clickedAt: Date?
    let ipAddress: String?
    let userAgent: String?
    let referer: String?
    let country: String?
    let city: String?
}

struct DailyStat: Codable, Identifiable, Hashable {
    // Date-only string like "2026-07-12"
    let date: String
    let clicks: Int
    let uniqueClicks: Int

    var id: String { date }
}

struct Referrer: Codable, Identifiable, Hashable {
    let referer: String
    let count: Int

    var id: String { referer }
}

struct EditRecord: Codable, Identifiable, Hashable {
    let id: Int
    let urlId: Int
    let oldUrl: String
    let newUrl: String
    let oldTitle: String?
    let newTitle: String?
    let editedAt: Date?
    let editReason: String?
}

// MARK: - Response envelopes

struct LinkListResponse: Codable {
    let urls: [ShortLink]
    let total: Int
    let page: Int
    let pages: Int
    let hasNext: Bool
    let hasPrev: Bool
}

struct CreateLinkResponse: Codable {
    let shortUrl: String
    let shortCode: String
    let originalUrl: String
    let title: String?
    let description: String?
    let tags: [String]?
}

struct EditLinkResponse: Codable {
    let success: Bool
    let message: String?
    let url: ShortLink
}

struct StatsResponse: Codable {
    let urlInfo: ShortLink
    let totalClicks: Int
    let recentClicks: [ClickRecord]
    let dailyStats: [DailyStat]
    let topReferrers: [Referrer]
}

struct HistoryResponse: Codable {
    let url: ShortLink
    let editHistory: [EditRecord]
}

struct TagsResponse: Codable {
    let tags: [String]
}

struct HealthResponse: Codable {
    let status: String
    let timestamp: Date?
    let version: String?
    // Only present when authenticated
    let totalUrls: Int?
    let totalClicks: Int?
    let authType: String?
}

struct LoginResponse: Codable {
    let success: Bool?
    let message: String?
    let apiKey: String?
}

struct VerifyResponse: Codable {
    let success: Bool
    let authType: String?
}

struct RegenerateKeyResponse: Codable {
    let success: Bool
    let message: String?
    let newApiKey: String
}

struct SimpleResponse: Codable {
    let success: Bool?
    let message: String?
}

struct APIErrorBody: Codable {
    let error: String?
    let message: String?
    let code: String?
}

// MARK: - Requests

struct CreateLinkRequest: Encodable {
    let url: String
    let customAlias: String?
    let title: String?
    let description: String?
    let tags: [String]?
}

struct EditLinkRequest: Encodable {
    let url: String
    let title: String?
    let description: String?
    let tags: [String]
    let reason: String?
}

struct LoginRequest: Encodable {
    let password: String
}

// MARK: - Sorting

enum LinkSortField: String, CaseIterable, Identifiable {
    case createdAt = "created_at"
    case clicks
    case updatedAt = "updated_at"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .createdAt: return "Date Created"
        case .clicks: return "Clicks"
        case .updatedAt: return "Last Updated"
        }
    }
}

enum SortOrder: String {
    case asc, desc
}

// MARK: - Date parsing

/// The API emits naive UTC timestamps (`datetime.utcnow().isoformat()`), e.g.
/// "2026-07-12T17:15:00.123456", with no timezone suffix, and date-only strings
/// for daily stats. Parse all variants as UTC.
enum APIDate {
    private static func formatter(_ format: String) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(identifier: "UTC")
        f.dateFormat = format
        return f
    }

    private static let formatters: [DateFormatter] = [
        formatter("yyyy-MM-dd'T'HH:mm:ss.SSSSSS"),
        formatter("yyyy-MM-dd'T'HH:mm:ss"),
        formatter("yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXXXX"),
        formatter("yyyy-MM-dd'T'HH:mm:ssXXXXX"),
        formatter("yyyy-MM-dd"),
    ]

    static func parse(_ string: String) -> Date? {
        for f in formatters {
            if let date = f.date(from: string) { return date }
        }
        return nil
    }

    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let raw = try container.decode(String.self)
            guard let date = APIDate.parse(raw) else {
                throw DecodingError.dataCorruptedError(
                    in: container,
                    debugDescription: "Unrecognized date format: \(raw)"
                )
            }
            return date
        }
        return decoder
    }()

    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()
}
