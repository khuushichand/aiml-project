import ICU, { type IcuConfig } from "i18next-icu"
import type { i18n, InterpolationOptions } from "i18next"

declare module "i18next-icu" {
  interface IcuInstance<TOptions = IcuConfig> {
    parse(
      res: string,
      options: Record<string, unknown>,
      lng: string,
      ns: string,
      key: string,
      info?: { resolved?: { res?: string } }
    ): string
  }
}

// Bridge ICU formatting with existing {{var}} interpolation.
export default class ICUWithInterpolation extends ICU {
  private _i18next?: i18n
  private interpolationOptions?: InterpolationOptions

  init(i18next: i18n, options?: IcuConfig) {
    super.init(i18next, options)
    // Store the i18next instance so we can lazily access the interpolator
    // in parse(). At init() time, services.interpolator may not exist yet.
    this._i18next = i18next
    this.interpolationOptions = i18next?.options?.interpolation
  }

  parse(
    res: string,
    options: Record<string, unknown>,
    lng: string,
    ns: string,
    key: string,
    info?: { resolved?: { res?: string } }
  ) {
    const interpolationOptions =
      (options as { interpolation?: InterpolationOptions })?.interpolation ??
      this.interpolationOptions ??
      {}
    // Lazily resolve the interpolator from the i18next instance at parse time,
    // since it may not be available when init() runs.
    const interpolator = this._i18next?.services?.interpolator
    const interpolated =
      typeof res === "string" && interpolator
        ? interpolator.interpolate(
            res,
            options as Record<string, unknown>,
            lng,
            interpolationOptions
          )
        : res
    return super.parse(interpolated, options, lng, ns, key, info)
  }
}
