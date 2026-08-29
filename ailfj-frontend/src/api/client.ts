import axios from 'axios'

export const client = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

const AUTH_PAGES = ["/login", "/register"]

// The access token cookie is short-lived on purpose (see backend/app/config.py) -
// a 401 here usually just means it expired, not that the session is over. Try a
// silent refresh once before giving up and sending the user back to /login.
let refreshInFlight: Promise<boolean> | null = null

function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = client
      .post('/auth/refresh')
      .then(() => true)
      .catch(() => false)
      .finally(() => { refreshInFlight = null })
  }
  return refreshInFlight
}

client.interceptors.response.use(
  (res) => res,
  async (err) => {
    // A 401 on the "who am I" probe is expected for anonymous visitors on any public
    // page (landing, reset-password, ...) - UserProvider already handles it gracefully.
    // Only force a redirect when an actually authenticated action fails, i.e. the
    // user's session expired mid-use.
    const isMeProbe = err.config?.url?.endsWith('/users/me')
    const isRefreshCall = err.config?.url?.endsWith('/auth/refresh')
    const isAuthPage = AUTH_PAGES.includes(window.location.pathname)

    if (err.response?.status === 401 && !isMeProbe && !isRefreshCall && !isAuthPage && !err.config?._retry) {
      const refreshed = await refreshAccessToken()
      if (refreshed) {
        err.config._retry = true
        return client(err.config)
      }
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)