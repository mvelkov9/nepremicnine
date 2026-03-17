import { getProxyRequestHeaders, proxyRequest } from 'h3'

export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  return proxyRequest(event, `${config.backendUrl}${event.node.req.url}`, {
    headers: getProxyRequestHeaders(event),
  })
})
