'use client'

import { useEffect, useState } from 'react'
import {
  APIProvider,
  InfoWindow,
  Map,
  Marker,
  useMap,
  useMapsLibrary,
} from '@vis.gl/react-google-maps'
import type { Dataset, Route, Stop } from '@/types'

// ---------------------------------------------------------------------------
// Route polylines — drawn imperatively so Google Maps owns the lifecycle
// ---------------------------------------------------------------------------
function RoutePolylines({
  routes,
  allStops,
  schoolLat,
  schoolLng,
}: {
  routes: Route[]
  allStops: Stop[]
  schoolLat: number
  schoolLng: number
}) {
  const map = useMap()
  const mapsLib = useMapsLibrary('maps')

  useEffect(() => {
    if (!map || !mapsLib) return

    const stopIndex = new Map(allStops.map((s) => [s.stop_id, s]))

    const polylines = routes.map((route) => {
      const path = [...route.stops]
        .sort((a, b) => a.sequence - b.sequence)
        .flatMap((rs) => {
          const stop = stopIndex.get(rs.stop_id)
          return stop ? [{ lat: stop.lat, lng: stop.lng }] : []
        })
      // Draw a dashed leg from last stop to school
      path.push({ lat: schoolLat, lng: schoolLng })

      return new mapsLib.Polyline({
        path,
        strokeColor: route.color,
        strokeOpacity: 0.88,
        strokeWeight: 5,
        map,
        zIndex: 5,
      })
    })

    return () => polylines.forEach((p) => p.setMap(null))
  }, [map, mapsLib, routes, allStops, schoolLat, schoolLng])

  return null
}

// ---------------------------------------------------------------------------
// Fits map bounds to the active stops + school on dataset change
// ---------------------------------------------------------------------------
function BoundsFitter({
  datasetId,
  allStops,
  schoolLat,
  schoolLng,
}: {
  datasetId: string
  allStops: Stop[]
  schoolLat: number
  schoolLng: number
}) {
  const map = useMap()
  const mapsLib = useMapsLibrary('maps')

  useEffect(() => {
    if (!map || !mapsLib || !allStops.length) return
    const bounds = new mapsLib.LatLngBounds()
    allStops.forEach((s) => bounds.extend({ lat: s.lat, lng: s.lng }))
    bounds.extend({ lat: schoolLat, lng: schoolLng })
    map.fitBounds(bounds, { top: 60, bottom: 60, left: 60, right: 60 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, mapsLib, datasetId]) // re-fit only when dataset changes

  return null
}

// ---------------------------------------------------------------------------
// Stop marker with click-to-open info window
// ---------------------------------------------------------------------------
function StopMarker({ stop, color }: { stop: Stop; color: string }) {
  const [open, setOpen] = useState(false)

  const iconUrl = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18">` +
      `<circle cx="9" cy="9" r="7" fill="${color}" stroke="white" stroke-width="2.5"/>` +
      `</svg>`,
  )}`

  return (
    <>
      <Marker
        position={{ lat: stop.lat, lng: stop.lng }}
        icon={{ url: iconUrl }}
        onClick={() => setOpen((v) => !v)}
        zIndex={10}
      />
      {open && (
        <InfoWindow
          position={{ lat: stop.lat, lng: stop.lng }}
          onCloseClick={() => setOpen(false)}
        >
          <div className="p-1 min-w-[140px]">
            <p className="font-semibold text-gray-900 text-sm leading-tight">
              {stop.name}
            </p>
            <p className="text-gray-500 text-xs mt-1">
              {stop.estimated_riders} estimated riders
            </p>
            <p className="text-gray-400 text-xs">Zone {stop.zone_id}</p>
          </div>
        </InfoWindow>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// School destination marker
// ---------------------------------------------------------------------------
function SchoolMarker({
  lat,
  lng,
  name,
}: {
  lat: number
  lng: number
  name: string
}) {
  const [open, setOpen] = useState(false)

  // Pin-shaped marker with "S" — works cross-browser without emoji rendering issues
  const iconUrl = `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="34" height="44" viewBox="0 0 34 44">` +
      `<path d="M17 0C7.611 0 0 7.611 0 17c0 11.25 17 27 17 27s17-15.75 17-27C34 7.611 26.389 0 17 0z" fill="#1d4ed8" stroke="white" stroke-width="1.5"/>` +
      `<circle cx="17" cy="17" r="9" fill="white"/>` +
      `<text x="17" y="22" text-anchor="middle" font-size="12" font-weight="700" fill="#1d4ed8" font-family="Arial,sans-serif">S</text>` +
      `</svg>`,
  )}`

  return (
    <>
      <Marker
        position={{ lat, lng }}
        icon={{ url: iconUrl }}
        onClick={() => setOpen((v) => !v)}
        zIndex={100}
      />
      {open && (
        <InfoWindow
          position={{ lat, lng }}
          onCloseClick={() => setOpen(false)}
        >
          <div className="p-1">
            <p className="font-bold text-gray-900 text-sm">{name}</p>
            <p className="text-gray-400 text-xs">Destination school</p>
          </div>
        </InfoWindow>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Legend overlay (rendered outside APIProvider as an HTML overlay)
// ---------------------------------------------------------------------------
function Legend({ routes }: { routes: Route[] }) {
  return (
    <div className="absolute bottom-8 left-4 z-10 rounded-xl bg-white shadow-lg p-3 min-w-[168px] pointer-events-none">
      <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-widest mb-2">
        Routes
      </p>
      {routes.map((route) => (
        <div key={route.route_id} className="flex items-center gap-2 mb-1.5">
          <div
            className="h-[5px] w-8 rounded-full flex-shrink-0"
            style={{ background: route.color }}
          />
          <span className="text-xs text-gray-700 truncate">{route.name}</span>
        </div>
      ))}
      <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-100">
        <div className="w-4 h-4 rounded-full bg-blue-700 flex-shrink-0 flex items-center justify-center">
          <span className="text-[9px] font-bold text-white">S</span>
        </div>
        <span className="text-xs text-gray-700">School</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------
export default function GoogleMapView({
  dataset,
  activeRoutes,
}: {
  dataset: Dataset
  activeRoutes: Route[]
}) {
  const apiKey = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? ''

  // Build stop-color lookup for current scenario
  const stopColorMap = new Map<string, string>()
  activeRoutes.forEach((route) =>
    route.stops.forEach((rs) => stopColorMap.set(rs.stop_id, route.color)),
  )

  const activeStopIds = new Set(
    activeRoutes.flatMap((r) => r.stops.map((s) => s.stop_id)),
  )
  const activeStops = dataset.stops.filter((s) => activeStopIds.has(s.stop_id))

  if (!apiKey) {
    return (
      <div className="flex h-full items-center justify-center bg-gray-800">
        <div className="text-center p-8 max-w-sm">
          <p className="text-3xl mb-3">🗺️</p>
          <p className="font-semibold text-gray-200 mb-2">
            Google Maps API Key Required
          </p>
          <p className="text-sm text-gray-400">
            Add{' '}
            <code className="bg-gray-700 text-gray-200 px-1.5 py-0.5 rounded text-xs">
              NEXT_PUBLIC_GOOGLE_MAPS_API_KEY
            </code>{' '}
            to{' '}
            <code className="bg-gray-700 text-gray-200 px-1.5 py-0.5 rounded text-xs">
              frontend/.env.local
            </code>
          </p>
          <p className="text-xs text-gray-500 mt-3">
            Enable the Maps JavaScript API in Google Cloud Console
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative h-full w-full">
      <APIProvider apiKey={apiKey}>
        <Map
          key={dataset.dataset_id}
          style={{ width: '100%', height: '100%' }}
          defaultCenter={{ lat: dataset.school_lat, lng: dataset.school_lng }}
          defaultZoom={13}
          gestureHandling="greedy"
          mapTypeControl={false}
          streetViewControl={false}
          fullscreenControl={false}
        >
          <BoundsFitter
            datasetId={dataset.dataset_id}
            allStops={activeStops}
            schoolLat={dataset.school_lat}
            schoolLng={dataset.school_lng}
          />
          <RoutePolylines
            routes={activeRoutes}
            allStops={dataset.stops}
            schoolLat={dataset.school_lat}
            schoolLng={dataset.school_lng}
          />
          {activeStops.map((stop) => (
            <StopMarker
              key={stop.stop_id}
              stop={stop}
              color={stopColorMap.get(stop.stop_id) ?? '#6b7280'}
            />
          ))}
          <SchoolMarker
            lat={dataset.school_lat}
            lng={dataset.school_lng}
            name={dataset.school_name}
          />
        </Map>
      </APIProvider>

      <Legend routes={activeRoutes} />
    </div>
  )
}
