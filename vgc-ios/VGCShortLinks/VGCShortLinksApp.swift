import SwiftUI

@main
struct VGCShortLinksApp: App {
    @StateObject private var session = SessionStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var session: SessionStore

    var body: some View {
        if session.isAuthenticated {
            MainTabView()
                .id(session.apiKey) // rebuild view state after re-login
        } else {
            LoginView()
        }
    }
}

struct MainTabView: View {
    @EnvironmentObject private var session: SessionStore

    var body: some View {
        TabView {
            LinkListView(viewModel: LinksViewModel(client: session.client))
                .tabItem { Label("Links", systemImage: "link") }

            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
    }
}
