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

    if (err.response?.status === 401 && !isRefreshCall && !isAuthPage && !err.config?._retry) {
      // Always attempt a silent refresh first, even for /users/me - an expired
      // access token on an actually-logged-in user (refresh cookie still valid
      // for up to 30 days) must not be mistaken for "never logged in" just
      // because /users/me happened to be the first call to hit the 401.
      const refreshed = await refreshAccessToken()
      if (refreshed) {
        err.config._retry = true
        return client(err.config)
      }
      // Refresh itself failed (no/invalid refresh cookie) - only force a hard
      // redirect for an actually authenticated action. A failed /users/me
      // probe here is the genuine "anonymous visitor on a public page" case;
      // let it reject normally so UserProvider just renders logged-out.
      if (!isMeProbe) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)