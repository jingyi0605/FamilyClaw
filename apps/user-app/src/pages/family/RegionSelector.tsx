import { useEffect, useMemo, useState } from 'react';
import { useI18n } from '../../runtime';
import { getPageMessage } from '../../runtime/h5-shell/i18n/pageMessageUtils';
import { api } from './api';
import type { RegionNode } from './types';

export const DEFAULT_REGION_PROVIDER = 'builtin.cn-mainland';
export const DEFAULT_REGION_COUNTRY = 'CN';

export type RegionSelectionFormValue = {
  countryCode: string;
  provinceCode: string;
  cityCode: string;
  districtCode: string;
};

type RegionSelectorProps = {
  value: RegionSelectionFormValue;
  onChange: (value: RegionSelectionFormValue) => void;
  disabled?: boolean;
};

export function RegionSelector({ value, onChange, disabled = false }: RegionSelectorProps) {
  const { locale } = useI18n();
  const [provinces, setProvinces] = useState<RegionNode[]>([]);
  const [cities, setCities] = useState<RegionNode[]>([]);
  const [districts, setDistricts] = useState<RegionNode[]>([]);
  const [loading, setLoading] = useState({ provinces: false, cities: false, districts: false });
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(current => ({ ...current, provinces: true }));
    setError('');
    void api.listRegionCatalog({
      provider_code: DEFAULT_REGION_PROVIDER,
      country_code: value.countryCode || DEFAULT_REGION_COUNTRY,
      admin_level: 'province',
    }).then(result => {
      if (cancelled) return;
      setProvinces(result);
    }).catch(regionError => {
      if (cancelled) return;
      setError(regionError instanceof Error ? regionError.message : getPageMessage(locale, 'family.regionSelector.loadProvincesFailure'));
    }).finally(() => {
      if (cancelled) return;
      setLoading(current => ({ ...current, provinces: false }));
    });

    return () => {
      cancelled = true;
    };
  }, [value.countryCode]);

  useEffect(() => {
    if (!value.provinceCode) {
      setCities([]);
      return;
    }
    let cancelled = false;
    setLoading(current => ({ ...current, cities: true }));
    setError('');
    void api.listRegionCatalog({
      provider_code: DEFAULT_REGION_PROVIDER,
      country_code: value.countryCode || DEFAULT_REGION_COUNTRY,
      parent_region_code: value.provinceCode,
      admin_level: 'city',
    }).then(result => {
      if (cancelled) return;
      setCities(result);
    }).catch(regionError => {
      if (cancelled) return;
      setError(regionError instanceof Error ? regionError.message : getPageMessage(locale, 'family.regionSelector.loadCitiesFailure'));
    }).finally(() => {
      if (cancelled) return;
      setLoading(current => ({ ...current, cities: false }));
    });

    return () => {
      cancelled = true;
    };
  }, [value.countryCode, value.provinceCode]);

  useEffect(() => {
    if (!value.cityCode) {
      setDistricts([]);
      return;
    }
    let cancelled = false;
    setLoading(current => ({ ...current, districts: true }));
    setError('');
    void api.listRegionCatalog({
      provider_code: DEFAULT_REGION_PROVIDER,
      country_code: value.countryCode || DEFAULT_REGION_COUNTRY,
      parent_region_code: value.cityCode,
      admin_level: 'district',
    }).then(result => {
      if (cancelled) return;
      setDistricts(result);
    }).catch(regionError => {
      if (cancelled) return;
      setError(regionError instanceof Error ? regionError.message : getPageMessage(locale, 'family.regionSelector.loadDistrictsFailure'));
    }).finally(() => {
      if (cancelled) return;
      setLoading(current => ({ ...current, districts: false }));
    });

    return () => {
      cancelled = true;
    };
  }, [value.cityCode, value.countryCode]);

  const selectedSummary = useMemo(() => {
    const province = provinces.find(item => item.region_code === value.provinceCode)?.name;
    const city = cities.find(item => item.region_code === value.cityCode)?.name;
    const district = districts.find(item => item.region_code === value.districtCode)?.name;
    return [province, city, district].filter(Boolean).join(' / ');
  }, [cities, districts, provinces, value.cityCode, value.districtCode, value.provinceCode]);

  return (
    <div className="form-group">
      <label>{getPageMessage(locale, 'family.regionSelector.regionLabel')}</label>
      <div className="setup-form-grid">
        <div className="form-group">
          <label htmlFor="region-country">{getPageMessage(locale, 'family.regionSelector.countryLabel')}</label>
          <select
            id="region-country"
            className="form-select"
            value={value.countryCode || DEFAULT_REGION_COUNTRY}
            disabled={disabled}
            onChange={event => onChange({ countryCode: event.target.value, provinceCode: '', cityCode: '', districtCode: '' })}
          >
            <option value="CN">{getPageMessage(locale, 'family.regionSelector.countryChina')}</option>
          </select>
          <div className="form-hint">{getPageMessage(locale, 'family.regionSelector.countryHint')}</div>
        </div>
      </div>
      <div className="setup-form-grid">
        <div className="form-group">
          <label htmlFor="region-province">{getPageMessage(locale, 'family.regionSelector.provinceLabel')}</label>
          <select
            id="region-province"
            className="form-select"
            value={value.provinceCode}
            disabled={disabled || loading.provinces}
            onChange={event => onChange({ countryCode: value.countryCode || DEFAULT_REGION_COUNTRY, provinceCode: event.target.value, cityCode: '', districtCode: '' })}
          >
            <option value="">{getPageMessage(locale, 'family.regionSelector.provincePlaceholder')}</option>
            {provinces.map(item => (
              <option key={item.region_code} value={item.region_code}>{item.name}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="region-city">{getPageMessage(locale, 'family.regionSelector.cityLabel')}</label>
          <select
            id="region-city"
            className="form-select"
            value={value.cityCode}
            disabled={disabled || !value.provinceCode || loading.cities}
            onChange={event => onChange({ countryCode: value.countryCode || DEFAULT_REGION_COUNTRY, provinceCode: value.provinceCode, cityCode: event.target.value, districtCode: '' })}
          >
            <option value="">{getPageMessage(locale, 'family.regionSelector.cityPlaceholder')}</option>
            {cities.map(item => (
              <option key={item.region_code} value={item.region_code}>{item.name}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="form-group">
        <label htmlFor="region-district">{getPageMessage(locale, 'family.regionSelector.districtLabel')}</label>
        <select
          id="region-district"
          className="form-select"
          value={value.districtCode}
          disabled={disabled || !value.cityCode || loading.districts}
          onChange={event => onChange({ countryCode: value.countryCode || DEFAULT_REGION_COUNTRY, provinceCode: value.provinceCode, cityCode: value.cityCode, districtCode: event.target.value })}
        >
          <option value="">{getPageMessage(locale, 'family.regionSelector.districtPlaceholder')}</option>
          {districts.map(item => (
            <option key={item.region_code} value={item.region_code}>{item.name}</option>
          ))}
        </select>
      </div>
      <div className="form-hint">{selectedSummary || getPageMessage(locale, 'family.regionSelector.summaryPlaceholder')}</div>
      {error && <div className="form-error">{error}</div>}
    </div>
  );
}
