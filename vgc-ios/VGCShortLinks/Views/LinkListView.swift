import SwiftUI
import UIKit

struct LinkListView: View {
    @EnvironmentObject private var session: SessionStore
    @StateObject var viewModel: LinksViewModel
    @State private var showingCreate = false

    var body: some View {
        NavigationStack {
            Group {
                if viewModel.links.isEmpty && viewModel.isLoading {
                    ProgressView("Loading links…")
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if viewModel.links.isEmpty {
                    emptyState
                } else {
                    linkList
                }
            }
            .navigationTitle("Short Links")
            .searchable(text: $viewModel.searchText, prompt: "Search links")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { sortMenu }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showingCreate = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showingCreate) {
                CreateLinkView { created in
                    viewModel.upsert(created)
                    Task { await viewModel.loadTags() }
                }
                .environmentObject(session)
            }
            .navigationDestination(for: ShortLink.self) { link in
                LinkDetailView(link: link) { updated in
                    viewModel.upsert(updated)
                } onDelete: { deleted in
                    Task { await viewModel.reload() }
                    _ = deleted
                }
                .environmentObject(session)
            }
            .task { await viewModel.initialLoad() }
            .refreshable {
                await viewModel.reload()
                await viewModel.loadTags()
            }
            .alert(
                "Error",
                isPresented: Binding(
                    get: { viewModel.errorMessage != nil },
                    set: { if !$0 { viewModel.errorMessage = nil } }
                )
            ) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(viewModel.errorMessage ?? "")
            }
        }
    }

    private var linkList: some View {
        List {
            if !viewModel.tagFilter.isEmpty {
                HStack {
                    Text("Tag: \(viewModel.tagFilter)")
                        .font(.callout)
                    Spacer()
                    Button("Clear") { viewModel.tagFilter = "" }
                        .font(.callout)
                }
            }

            ForEach(viewModel.links) { link in
                NavigationLink(value: link) {
                    LinkRowView(link: link, baseURL: session.baseURL)
                }
                .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                    Button(role: .destructive) {
                        Task { await viewModel.delete(link) }
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                    Button {
                        UIPasteboard.general.string = link.shortURL(base: session.baseURL).absoluteString
                    } label: {
                        Label("Copy", systemImage: "doc.on.doc")
                    }
                    .tint(.blue)
                }
                .task { await viewModel.loadMoreIfNeeded(current: link) }
            }

            if viewModel.isLoading && !viewModel.links.isEmpty {
                HStack {
                    Spacer()
                    ProgressView()
                    Spacer()
                }
            }

            Text("\(viewModel.total) link\(viewModel.total == 1 ? "" : "s")")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .frame(maxWidth: .infinity)
                .listRowBackground(Color.clear)
        }
        .listStyle(.plain)
    }

    private var emptyState: some View {
        ContentUnavailableView {
            Label("No Links", systemImage: "link")
        } description: {
            Text(viewModel.searchText.isEmpty
                 ? "Create your first short link with the + button."
                 : "No links match “\(viewModel.searchText)”.")
        } actions: {
            if viewModel.searchText.isEmpty {
                Button("Create Link") { showingCreate = true }
                    .buttonStyle(.borderedProminent)
            }
        }
    }

    private var sortMenu: some View {
        Menu {
            Picker("Sort by", selection: $viewModel.sortField) {
                ForEach(LinkSortField.allCases) { field in
                    Text(field.label).tag(field)
                }
            }
            Divider()
            Button {
                viewModel.sortOrder = viewModel.sortOrder == .desc ? .asc : .desc
            } label: {
                Label(
                    viewModel.sortOrder == .desc ? "Descending" : "Ascending",
                    systemImage: viewModel.sortOrder == .desc ? "arrow.down" : "arrow.up"
                )
            }
            if !viewModel.availableTags.isEmpty {
                Divider()
                Menu("Filter by Tag") {
                    Button("All Tags") { viewModel.tagFilter = "" }
                    ForEach(viewModel.availableTags, id: \.self) { tag in
                        Button(tag) { viewModel.tagFilter = tag }
                    }
                }
            }
        } label: {
            Image(systemName: "line.3.horizontal.decrease.circle")
        }
    }
}

struct LinkRowView: View {
    let link: ShortLink
    let baseURL: URL

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(link.displayTitle)
                .font(.headline)
                .lineLimit(1)

            Text(link.shortURL(base: baseURL).absoluteString
                .replacingOccurrences(of: "https://", with: ""))
                .font(.subheadline)
                .foregroundStyle(.tint)
                .lineLimit(1)

            HStack(spacing: 12) {
                Label("\(link.clicks)", systemImage: "cursorarrow.click.2")
                if let created = link.createdAt {
                    Text(created, style: .relative) + Text(" ago")
                }
                if !link.tags.isEmpty {
                    Label(link.tags.joined(separator: ", "), systemImage: "tag")
                        .lineLimit(1)
                }
            }
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }
}
