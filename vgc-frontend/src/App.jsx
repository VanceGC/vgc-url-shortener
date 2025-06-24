import { useState, useEffect } from 'react'
import './App.css'

const API_BASE = window.location.origin + '/api'

function App() {
  // Authentication state
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [authLoading, setAuthLoading] = useState(true)
  const [apiKey, setApiKey] = useState('')
  const [showApiKey, setShowApiKey] = useState(false)
  
  // Login state
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  
  // URL shortener state
  const [url, setUrl] = useState('')
  const [customAlias, setCustomAlias] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [tags, setTags] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  
  // URL management state
  const [urls, setUrls] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedUrl, setSelectedUrl] = useState(null)
  const [editingUrl, setEditingUrl] = useState(null)
  const [showHistory, setShowHistory] = useState(false)
  const [urlHistory, setUrlHistory] = useState([])
  const [activeTab, setActiveTab] = useState('create')

  // Check authentication status on load
  useEffect(() => {
    checkAuthStatus()
  }, [])

  const checkAuthStatus = async () => {
    try {
      const response = await fetch(`${API_BASE}/auth/status`, {
        credentials: 'include'
      })
      const data = await response.json()
      
      if (data.authenticated) {
        setIsAuthenticated(true)
        if (data.api_key) {
          setApiKey(data.api_key)
        }
        loadUrls()
      }
    } catch (error) {
      console.error('Auth check failed:', error)
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogin = async (e) => {
    e.preventDefault()
    setLoginLoading(true)
    setLoginError('')

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({ password })
      })

      const data = await response.json()

      if (response.ok) {
        setIsAuthenticated(true)
        setApiKey(data.api_key)
        setPassword('')
        loadUrls()
      } else {
        setLoginError(data.error || 'Login failed')
      }
    } catch (error) {
      setLoginError('Network error occurred')
    } finally {
      setLoginLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      })
      setIsAuthenticated(false)
      setApiKey('')
      setUrls([])
      setResult(null)
      setActiveTab('create')
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }

  const loadUrls = async () => {
    try {
      const response = await fetch(`${API_BASE}/urls?limit=20`, {
        credentials: 'include'
      })
      if (response.ok) {
        const data = await response.json()
        setUrls(data.urls || [])
      }
    } catch (error) {
      console.error('Failed to load URLs:', error)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const payload = {
        url: url.trim(),
        title: title.trim(),
        description: description.trim(),
        tags: tags.split(',').map(tag => tag.trim()).filter(tag => tag)
      }

      if (customAlias.trim()) {
        payload.custom_alias = customAlias.trim()
      }

      const response = await fetch(`${API_BASE}/shorten`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify(payload)
      })

      const data = await response.json()

      if (response.ok) {
        setResult(data)
        setUrl('')
        setCustomAlias('')
        setTitle('')
        setDescription('')
        setTags('')
        loadUrls() // Refresh the list
      } else {
        setError(data.error || 'Failed to shorten URL')
      }
    } catch (error) {
      setError('Network error occurred')
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
  }

  const viewUrlHistory = async (shortCode) => {
    try {
      const response = await fetch(`${API_BASE}/history/${shortCode}`, {
        credentials: 'include'
      })
      if (response.ok) {
        const data = await response.json()
        setUrlHistory(data.edit_history || [])
        setSelectedUrl(data.url)
        setShowHistory(true)
      }
    } catch (error) {
      console.error('Failed to load URL history:', error)
    }
  }

  const editUrl = async (shortCode, updates) => {
    try {
      const response = await fetch(`${API_BASE}/edit/${shortCode}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify(updates)
      })

      if (response.ok) {
        loadUrls()
        setEditingUrl(null)
      } else {
        const data = await response.json()
        setError(data.error || 'Failed to update URL')
      }
    } catch (error) {
      setError('Network error occurred')
    }
  }

  const deleteUrl = async (shortCode) => {
    if (!confirm('Are you sure you want to delete this URL?')) return

    try {
      const response = await fetch(`${API_BASE}/delete/${shortCode}`, {
        method: 'DELETE',
        credentials: 'include'
      })

      if (response.ok) {
        loadUrls()
      }
    } catch (error) {
      console.error('Failed to delete URL:', error)
    }
  }

  const regenerateApiKey = async () => {
    if (!confirm('Are you sure you want to regenerate the API key? This will invalidate the current key.')) return

    try {
      const response = await fetch(`${API_BASE}/auth/regenerate-api-key`, {
        method: 'POST',
        credentials: 'include'
      })

      if (response.ok) {
        const data = await response.json()
        setApiKey(data.new_api_key)
      }
    } catch (error) {
      console.error('Failed to regenerate API key:', error)
    }
  }

  if (authLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="max-w-md w-full space-y-8 p-8">
          <div className="text-center">
            <h1 className="text-4xl font-bold text-gray-900 mb-2">VGC URL Shortener</h1>
            <p className="text-gray-600">Please log in to continue</p>
          </div>
          
          <form onSubmit={handleLogin} className="mt-8 space-y-6">
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="Enter password"
              />
            </div>
            
            {loginError && (
              <div className="text-red-600 text-sm text-center">{loginError}</div>
            )}
            
            <button
              type="submit"
              disabled={loginLoading}
              className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
            >
              {loginLoading ? 'Logging in...' : 'Log In'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900">VGC URL Shortener</h1>
          <div className="flex items-center space-x-4">
            <button
              onClick={() => setShowApiKey(!showApiKey)}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
            >
              {showApiKey ? 'Hide' : 'Show'} API Key
            </button>
            <button
              onClick={handleLogout}
              className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              Logout
            </button>
          </div>
        </div>

        {/* API Key Section */}
        {showApiKey && (
          <div className="bg-white rounded-lg shadow-md p-6 mb-8">
            <h2 className="text-xl font-semibold mb-4">API Key for Automation</h2>
            <div className="bg-gray-50 p-4 rounded-lg mb-4">
              <div className="flex items-center justify-between">
                <code className="text-sm font-mono break-all">{apiKey}</code>
                <button
                  onClick={() => copyToClipboard(apiKey)}
                  className="ml-2 px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                >
                  Copy
                </button>
              </div>
            </div>
            <div className="text-sm text-gray-600 space-y-2">
              <p><strong>Usage:</strong> Include this key in your API requests</p>
              <p><strong>Header:</strong> <code>X-API-Key: {apiKey}</code></p>
              <p><strong>Example:</strong></p>
              <pre className="bg-gray-100 p-2 rounded text-xs overflow-x-auto">
{`curl -X POST https://vgc.to/api/shorten \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: ${apiKey}" \\
  -d '{"url": "https://example.com", "title": "My Link"}'`}
              </pre>
            </div>
            <button
              onClick={regenerateApiKey}
              className="mt-4 px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700 text-sm"
            >
              Regenerate API Key
            </button>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="flex space-x-1 mb-8">
          <button
            onClick={() => setActiveTab('create')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'create'
                ? 'bg-indigo-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            Create Short URL
          </button>
          <button
            onClick={() => setActiveTab('manage')}
            className={`px-6 py-3 rounded-lg font-medium transition-colors ${
              activeTab === 'manage'
                ? 'bg-indigo-600 text-white'
                : 'bg-white text-gray-700 hover:bg-gray-50'
            }`}
          >
            Manage URLs
          </button>
        </div>

        {/* Create URL Tab */}
        {activeTab === 'create' && (
          <div className="bg-white rounded-lg shadow-md p-8">
            <h2 className="text-2xl font-semibold mb-6">Create New Short URL</h2>
            
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label htmlFor="url" className="block text-sm font-medium text-gray-700 mb-2">
                  Original URL *
                </label>
                <input
                  id="url"
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  placeholder="https://example.com/very/long/url"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label htmlFor="customAlias" className="block text-sm font-medium text-gray-700 mb-2">
                    Custom Alias (optional)
                  </label>
                  <input
                    id="customAlias"
                    type="text"
                    value={customAlias}
                    onChange={(e) => setCustomAlias(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="my-custom-link"
                  />
                </div>

                <div>
                  <label htmlFor="title" className="block text-sm font-medium text-gray-700 mb-2">
                    Title (optional)
                  </label>
                  <input
                    id="title"
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="Page title"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-2">
                  Description (optional)
                </label>
                <textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  placeholder="Brief description of the link"
                />
              </div>

              <div>
                <label htmlFor="tags" className="block text-sm font-medium text-gray-700 mb-2">
                  Tags (optional)
                </label>
                <input
                  id="tags"
                  type="text"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  placeholder="tag1, tag2, tag3"
                />
              </div>

              {error && (
                <div className="text-red-600 text-sm">{error}</div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-indigo-600 text-white py-3 px-6 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 font-medium"
              >
                {loading ? 'Creating...' : 'Create Short URL'}
              </button>
            </form>

            {result && (
              <div className="mt-8 p-6 bg-green-50 border border-green-200 rounded-lg">
                <h3 className="text-lg font-semibold text-green-800 mb-4">URL Created Successfully!</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between bg-white p-3 rounded border">
                    <span className="font-mono text-sm">{result.short_url}</span>
                    <button
                      onClick={() => copyToClipboard(result.short_url)}
                      className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700"
                    >
                      Copy
                    </button>
                  </div>
                  {result.title && (
                    <p><strong>Title:</strong> {result.title}</p>
                  )}
                  <p><strong>Original URL:</strong> {result.original_url}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Manage URLs Tab */}
        {activeTab === 'manage' && (
          <div className="bg-white rounded-lg shadow-md p-8">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-semibold">Manage URLs</h2>
              <div className="flex items-center space-x-4">
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search URLs..."
                  className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
                <button
                  onClick={loadUrls}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                >
                  Refresh
                </button>
              </div>
            </div>

            <div className="space-y-4">
              {urls
                .filter(url => 
                  !searchTerm || 
                  url.original_url.toLowerCase().includes(searchTerm.toLowerCase()) ||
                  url.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
                  url.short_code.toLowerCase().includes(searchTerm.toLowerCase())
                )
                .map((url) => (
                <div key={url.id} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <span className="font-mono text-sm bg-gray-100 px-2 py-1 rounded">
                          vgc.to/{url.short_code}
                        </span>
                        <button
                          onClick={() => copyToClipboard(`https://vgc.to/${url.short_code}`)}
                          className="text-blue-600 hover:text-blue-800 text-sm"
                        >
                          Copy
                        </button>
                      </div>
                      <h3 className="font-medium text-gray-900">{url.title || 'Untitled'}</h3>
                      <p className="text-sm text-gray-600 break-all">{url.original_url}</p>
                      <div className="flex items-center space-x-4 mt-2 text-sm text-gray-500">
                        <span>{url.clicks} clicks</span>
                        <span>Created: {new Date(url.created_at).toLocaleDateString()}</span>
                        {url.tags && <span>Tags: {url.tags}</span>}
                      </div>
                    </div>
                    <div className="flex space-x-2 ml-4">
                      <button
                        onClick={() => viewUrlHistory(url.short_code)}
                        className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                      >
                        History
                      </button>
                      <button
                        onClick={() => setEditingUrl(url)}
                        className="px-3 py-1 bg-yellow-600 text-white text-sm rounded hover:bg-yellow-700"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => deleteUrl(url.short_code)}
                        className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {urls.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                No URLs found. Create your first short URL!
              </div>
            )}
          </div>
        )}

        {/* Edit URL Modal */}
        {editingUrl && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg p-6 w-full max-w-md">
              <h3 className="text-lg font-semibold mb-4">Edit URL</h3>
              <form onSubmit={(e) => {
                e.preventDefault()
                const formData = new FormData(e.target)
                editUrl(editingUrl.short_code, {
                  url: formData.get('url'),
                  title: formData.get('title'),
                  description: formData.get('description'),
                  reason: formData.get('reason')
                })
              }}>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">URL</label>
                    <input
                      name="url"
                      type="url"
                      defaultValue={editingUrl.original_url}
                      required
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
                    <input
                      name="title"
                      type="text"
                      defaultValue={editingUrl.title || ''}
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                    <textarea
                      name="description"
                      defaultValue={editingUrl.description || ''}
                      rows={3}
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Edit Reason</label>
                    <input
                      name="reason"
                      type="text"
                      placeholder="Why are you making this change?"
                      className="w-full px-3 py-2 border border-gray-300 rounded focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                </div>
                <div className="flex justify-end space-x-3 mt-6">
                  <button
                    type="button"
                    onClick={() => setEditingUrl(null)}
                    className="px-4 py-2 text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700"
                  >
                    Save Changes
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* URL History Modal */}
        {showHistory && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-96 overflow-y-auto">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold">Edit History</h3>
                <button
                  onClick={() => setShowHistory(false)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  ✕
                </button>
              </div>
              {selectedUrl && (
                <div className="mb-4 p-3 bg-gray-50 rounded">
                  <p><strong>Short URL:</strong> vgc.to/{selectedUrl.short_code}</p>
                  <p><strong>Current URL:</strong> {selectedUrl.original_url}</p>
                </div>
              )}
              <div className="space-y-3">
                {urlHistory.length > 0 ? (
                  urlHistory.map((edit, index) => (
                    <div key={index} className="border-l-4 border-blue-500 pl-4 py-2">
                      <div className="text-sm text-gray-600">
                        {new Date(edit.edited_at).toLocaleString()}
                      </div>
                      <div className="mt-1">
                        <p><strong>From:</strong> {edit.old_url}</p>
                        <p><strong>To:</strong> {edit.new_url}</p>
                        {edit.edit_reason && (
                          <p><strong>Reason:</strong> {edit.edit_reason}</p>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-gray-500">No edit history available.</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App

