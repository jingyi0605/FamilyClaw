import { useEffect, useMemo, useState } from 'react';
import { useI18n } from '../../runtime';
import { setupApi } from './setupApi';
import type { RegionNode } from './setupTypes';

export const DEFAULT_REGION_PROVIDER = 'builtin.cn-mainland';
export const DEFAULT_REGION_COUNTRY = 'CN';

export type RegionSelectionFormValue = {
  countryCode: string;
  provinceCode: string;
  cityCode: string;
  districtCode: string;
};

export function RegionSelector(props: {
  value: RegionSelectionFormValue;
  onChange: (value: RegionSelectionFormValue) => void;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const { value, onChange, disabled = false } = props;
  const [provinces, setProvinces] = useState<RegionNode[]>([]);
  const [cities, setCities] = useState<RegionNode[]>([]);
  const [districts, setDistricts] = useState<RegionNode[]>([]);
  const [loading, setLoading] = useState({ provinces: false, cities: false, districts: false });
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(current => ({ ...current, provinces: true }));
    setError('');
    void setupApi.listRegionCatalog({ provider_code: DEFAULT_REGION_PROVIDER, country_code: value.countryCode || DEFAULT_REGION_COUNTRY, admin_level: 'province' })
      .then(result => { if (!cancelled) setProvinces(result); })
      .catch(regionError => { if (!cancelled) setError(regionError instanceof Error ? regionError.message : t('setup.region.loadProvinceFailed')); })
      .finally(() => { if (!cancelled) setLoading(current => ({ ...current, provinces: false })); });
    return () => { cancelled = true; };
  }, [t, value.countryCode]);

  useEffect(() => {
    if (!value.provinceCode) { setCities([]); return; }
    let cancelled = false;
    setLoading(current => ({ ...current, cities: true }));
    setError('');
    void setupApi.listRegionCatalog({ provider_code: DEFAULT_REGION_PROVIDER, country_code: value.countryCode || DEFAULT_REGION_COUNTRY, parent_region_code: value.provinceCode, admin_level: 'city' })
      .then(result => { if (!cancelled) setCities(result); })
      .catch(regionError => { if (!cancelled) setError(regionError instanceof Error ? regionError.message : t('setup.region.loadCityFailed')); })
      .finally(() => { if (!cancelled) setLoading(current => ({ ...current, cities: false })); });
    return () => { cancelled = true; };
  }, [t, value.countryCode, value.provinceCode]);

  useEffect(() => {
    if (!value.cityCode) { setDistricts([]); return; }
    let cancelled = false;
    setLoading(current => ({ ...current, districts: true }));
    setError('');
    void setupApi.listRegionCatalog({ provider_code: DEFAULT_REGION_PROVIDER, country_code: value.countryCode || DEFAULT_REGION_COUNTRY, parent_region_code: value.cityCode, admin_level: 'district' })
      .then(result => { if (!cancelled) setDistricts(result); })
      .catch(regionError => { if (!cancelled) setError(regionError instanceof Error ? regionError.message : t('setup.region.loadDistrictFailed')); })
      .finally(() => { if (!cancelled) setLoading(current => ({ ...current, districts: false })); });
    return () => { cancelled = true; };
  }, [t, value.cityCode, value.countryCode]);

  const selectedSummary = useMemo(() => {
    const province = provinces.find(item => item.region_code === value.provinceCode)?.name;
    const city = cities.find(item => item.region_code === value.cityCode)?.name;
    const district = districts.find(item => item.region_code === value.districtCode)?.name;
    return [province, city, district].filter(Boolean).join(' / ');
  }, [cities, districts, provinces, value.cityCode, value.districtCode, value.provinceCode]);

  return (
    <div className="form-group">
      <label>{t('setup.region.label')}</label>
      <div className="setup-form-grid">
        <div className="form-group">
          <label htmlFor="region-country">{t('setup.region.countryLabel')}</label>
          <select id="region-country" className="form-select" value={value.countryCode || DEFAULT_REGION_COUNTRY} disabled={disabled} onChange={event => onChange({ countryCode: event.target.value, provinceCode: '', cityCode: '', districtCode: '' })}>
            <option value="CN">{t('setup.region.countryChina')}</option>
          </select>
          <div className="form-hint">{t('setup.region.countryHint')}</div>
        </div>
      </div>
      <div className="setup-form-grid">
        <div className="form-group">
          <label htmlFor="region-province">{t('setup.region.provinceLabel')}</label>
          <select id="region-province" className="form-select" value={value.provinceCode} disabled={disabled || loading.provinces} onChange={event => onChange({ countryCode: value.countryCode || DEFAULT_REGION_COUNTRY, provinceCode: event.target.value, cityCode: '', districtCode: '' })}>
            <option value="">{t('setup.region.provincePlaceholder')}</option>
            {provinces.map(item => <option key={item.region_code} value={item.region_code}>{item.name}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="region-city">{t('setup.region.cityLabel')}</label>
          <select id="region-city" className="form-select" value={value.cityCode} disabled={disabled || !value.provinceCode || loading.cities} onChange={event => onChange({ countryCode: value.countryCode || DEFAULT_REGION_COUNTRY, provinceCode: value.provinceCode, cityCode: event.target.value, districtCode: '' })}>
            <option value="">{t('setup.region.cityPlaceholder')}</option>
            {cities.map(item => <option key={item.region_code} value={item.region_code}>{item.name}</option>)}
          </select>
        </div>
      </div>
      <div className="form-group">
        <label htmlFor="region-district">{t('setup.region.districtLabel')}</label>
        <select id="region-district" className="form-select" value={value.districtCode} disabled={disabled || !value.cityCode || loading.districts} onChange={event => onChange({ countryCode: value.countryCode || DEFAULT_REGION_COUNTRY, provinceCode: value.provinceCode, cityCode: value.cityCode, districtCode: event.target.value })}>
          <option value="">{t('setup.region.districtPlaceholder')}</option>
          {districts.map(item => <option key={item.region_code} value={item.region_code}>{item.name}</option>)}
        </select>
      </div>
      <div className="form-hint">{selectedSummary || t('setup.region.summaryPlaceholder')}</div>
      {error ? <div className="form-error">{error}</div> : null}
    </div>
  );
}
