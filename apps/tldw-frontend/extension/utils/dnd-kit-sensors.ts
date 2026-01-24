import { useMemo } from "react"
import {
  configure,
  descriptor,
  type SensorConstructor,
  type SensorDescriptor,
  type SensorOptions
} from "@dnd-kit/abstract"

export const useSensor = <T extends SensorConstructor<any>>(
  sensor: T,
  options?: SensorOptions
): SensorDescriptor<any> =>
  useMemo(
    () => (options ? configure(sensor, options) : descriptor(sensor)),
    [sensor, options]
  )

export const useSensors = (
  ...sensors: Array<SensorDescriptor<any> | null | undefined>
): SensorDescriptor<any>[] =>
  useMemo(
    () => sensors.filter(Boolean) as SensorDescriptor<any>[],
    sensors
  )
