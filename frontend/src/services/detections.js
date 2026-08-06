function boxIou(first, second) {
  const left = Math.max(first.x, second.x)
  const top = Math.max(first.y, second.y)
  const right = Math.min(first.x + first.width, second.x + second.width)
  const bottom = Math.min(first.y + first.height, second.y + second.height)
  const intersection = Math.max(right - left, 0) * Math.max(bottom - top, 0)
  const union = first.width * first.height + second.width * second.height - intersection
  return union > 0 ? intersection / union : 0
}

export function addImageDimensions(result) {
  return result.detections.map((detection) => ({
    ...detection,
    imageWidth: result.image.width,
    imageHeight: result.image.height,
  }))
}

export function smoothDetections(previous, current, alpha = 0.45) {
  const available = new Set(previous.map((_, index) => index))

  return current.map((detection) => {
    let bestIndex = -1
    let bestIou = 0.2
    available.forEach((index) => {
      const score = boxIou(previous[index].box, detection.box)
      if (score > bestIou) {
        bestIou = score
        bestIndex = index
      }
    })

    if (bestIndex === -1) return detection
    available.delete(bestIndex)
    const oldDetection = previous[bestIndex]
    const oldBox = oldDetection.box
    const newBox = detection.box
    return {
      ...detection,
      confidence: oldDetection.name === detection.name
        ? oldDetection.confidence + alpha * (detection.confidence - oldDetection.confidence)
        : detection.confidence,
      box: {
        x: oldBox.x + alpha * (newBox.x - oldBox.x),
        y: oldBox.y + alpha * (newBox.y - oldBox.y),
        width: oldBox.width + alpha * (newBox.width - oldBox.width),
        height: oldBox.height + alpha * (newBox.height - oldBox.height),
      },
    }
  })
}
