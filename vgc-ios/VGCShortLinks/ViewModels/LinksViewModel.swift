import Foundation

/// Drives the paginated, searchable, sortable link list.
@MainActor
final class LinksViewModel: ObservableObject {
    @Published var links: [ShortLink] = []
    @Published var total = 0
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var searchText = "" {
        didSet { scheduleSearch() }
    }
    @Published var sortField: LinkSortField = .createdAt {
        didSet { Task { await reload() } }
    }
    @Published var sortOrder: SortOrder = .desc {
        didSet { Task { await reload() } }
    }
    @Published var tagFilter: String = "" {
        didSet { Task { await reload() } }
    }
    @Published var availableTags: [String] = []

    private let client: APIClient
    private let pageSize = 50
    private var page = 1
    private var hasNext = false
    private var searchTask: Task<Void, Never>?

    init(client: APIClient) {
        self.client = client
    }

    func initialLoad() async {
        guard links.isEmpty else { return }
        await reload()
        await loadTags()
    }

    func reload() async {
        page = 1
        isLoading = true
        errorMessage = nil
        do {
            let response = try await fetch(page: 1)
            links = response.urls
            total = response.total
            hasNext = response.hasNext
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func loadMoreIfNeeded(current link: ShortLink) async {
        guard hasNext, !isLoading, link.id == links.last?.id else { return }
        isLoading = true
        do {
            let response = try await fetch(page: page + 1)
            page = response.page
            hasNext = response.hasNext
            let existing = Set(links.map(\.id))
            links.append(contentsOf: response.urls.filter { !existing.contains($0.id) })
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func delete(_ link: ShortLink) async {
        do {
            _ = try await client.deleteLink(shortCode: link.shortCode)
            links.removeAll { $0.id == link.id }
            total = max(0, total - 1)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    /// Replace a link in-place after an edit, or prepend a newly created one.
    func upsert(_ link: ShortLink) {
        if let index = links.firstIndex(where: { $0.id == link.id }) {
            links[index] = link
        } else {
            links.insert(link, at: 0)
            total += 1
        }
    }

    func loadTags() async {
        availableTags = (try? await client.tags())?.tags ?? []
    }

    private func fetch(page: Int) async throws -> LinkListResponse {
        try await client.listLinks(
            page: page,
            limit: pageSize,
            search: searchText,
            tag: tagFilter,
            sort: sortField,
            order: sortOrder
        )
    }

    private func scheduleSearch() {
        searchTask?.cancel()
        searchTask = Task {
            try? await Task.sleep(for: .milliseconds(350))
            guard !Task.isCancelled else { return }
            await reload()
        }
    }
}
