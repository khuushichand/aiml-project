import { useMemo } from "react"
import {
  configure,
  descriptor,
  type SensorConstructor,
  type SensorDescriptor,
  type SensorOptions
} from "@dnd-kit/abstract"

export const useSensor = <T extends SensorConstructor<unknown>>(
  sensor: T,
  options?: SensorOptions
): SensorDescriptor<unknown> =>
  useMemo(
    () => (options ? configure(sensor, options) : descriptor(sensor)),
    [sensor, options]
  )

export const useSensors = (
  ...sensors: Array<SensorDescriptor<unknown> | null | undefined>
): SensorDescriptor<unknown>[] =>
  useMemo(
    () =>
      sensors.filter(
        (sensor): sensor is SensorDescriptor<unknown> => Boolean(sensor)
      ),
    [sensors]
  )
