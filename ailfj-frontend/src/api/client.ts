import axios from 'axios'

export const client = axios.create({
  baseURL: '/api',
  withCredentials: true,
})

const AUTH_PAGES = ["/login", "/register"]

client.interceptors.response.use(
  (res) => res,
  (err) => {
    // A 401 on the "who am I" probe is expected for anonymous visitors on any public
    // page (landing, reset-password, ...) - UserProvider already handles it gracefully.
    // Only force a redirect when an actually authenticated action fails, i.e. the
    // user's session expired mid-use.
    const isMeProbe = err.config?.url?.endsWith('/users/me')
    if (err.response?.status === 401 && !isMeProbe && !AUTH_PAGES.includes(window.location.pathname)) {
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)
