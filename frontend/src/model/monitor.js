import axios from 'axios'
import config from '/src/config.js'

const API = axios.create({
  baseURL: `${config.PROTOCOL}//${config.BACKEND}:${config.PORT}${config.BASEURL}`,
})

function listMonitoredPlaylists() {
  return API.get('/api/monitor/playlists')
}

function addMonitoredPlaylist(url, intervalMinutes = 60) {
  return API.post('/api/monitor/playlists', {
    url,
    interval_minutes: intervalMinutes,
  })
}

function updateMonitoredPlaylist(id, updates) {
  return API.patch(`/api/monitor/playlists/${id}`, updates)
}

function deleteMonitoredPlaylist(id) {
  return API.delete(`/api/monitor/playlists/${id}`)
}

function checkMonitoredPlaylist(id) {
  return API.post(`/api/monitor/playlists/${id}/check`)
}

function listMonitoredArtists() {
  return API.get('/api/monitor/artists')
}

function addMonitoredArtist(url, intervalMinutes = 1440) {
  return API.post('/api/monitor/artists', {
    url,
    interval_minutes: intervalMinutes,
  })
}

function updateMonitoredArtist(id, updates) {
  return API.patch(`/api/monitor/artists/${id}`, updates)
}

function deleteMonitoredArtist(id) {
  return API.delete(`/api/monitor/artists/${id}`)
}

function checkMonitoredArtist(id) {
  return API.post(`/api/monitor/artists/${id}/check`)
}

export default {
  listMonitoredPlaylists,
  addMonitoredPlaylist,
  updateMonitoredPlaylist,
  deleteMonitoredPlaylist,
  checkMonitoredPlaylist,
  listMonitoredArtists,
  addMonitoredArtist,
  updateMonitoredArtist,
  deleteMonitoredArtist,
  checkMonitoredArtist,
}
