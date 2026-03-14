import { useEffect, useMemo, useState } from 'react';
import { api } from '../lib/api';
import type { RegionNode } from '../lib/types';

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
      setError(regionError instanceof Error ? regionError.message : '加载省份失败');
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
      setError(regionError instanceof Error ? regionError.message : '加载城市失败');
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
      setError(regionError instanceof Error ? regionError.message : '加载区县失败');
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
      <label>所在地区</label>
      <div className="setup-form-grid">
        <div className="form-group">
          <label htmlFor="region-country">国家 / 地区</label>
          <select
            id="region-country"
            className="form-select"
            value={value.countryCode || DEFAULT_REGION_COUNTRY}
            disabled={disabled}
            onChange={event => onChange({ countryCode: event.target.value, provinceCode: '', cityCode: '', districtCode: '' })}
          >
            <option value="CN">中国</option>
          </select>
          <div className="form-hint">当前可选中国，已包含大陆、香港、澳门和台湾地区。</div>
        </div>
      </div>
      <div className="setup-form-grid">
        <div className="form-group">
          <label htmlFor="region-province">省级</label>
          <select
            id="region-province"
            className="form-select"
            value={value.provinceCode}
            disabled={disabled || loading.provinces}
            onChange={event => onChange({ countryCode: value.countryCode || DEFAULT_REGION_COUNTRY, provinceCode: event.target.value, cityCode: '', districtCode: '' })}
          >
            <option value="">请选择省级地区</option>
            {provinces.map(item => (
              <option key={item.region_code} value={item.region_code}>{item.name}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label htmlFor="region-city">市级</label>
          <select
            id="region-city"
            className="form-select"
            value={value.cityCode}
            disabled={disabled || !value.provinceCode || loading.cities}
            onChange={event => onChange({ countryCode: value.countryCode || DEFAULT_REGION_COUNTRY, provinceCode: value.provinceCode, cityCode: event.target.value, districtCode: '' })}
          >
            <option value="">请选择市级地区</option>
            {cities.map(item => (
              <option key={item.region_code} value={item.region_code}>{item.name}</option>
            ))}
          </select>
        </div>
      </div>
      <div className="form-group">
        <label htmlFor="region-district">区县</label>
        <select
          id="region-district"
          className="form-select"
          value={value.districtCode}
          disabled={disabled || !value.cityCode || loading.districts}
          onChange={event => onChange({ countryCode: value.countryCode || DEFAULT_REGION_COUNTRY, provinceCode: value.provinceCode, cityCode: value.cityCode, districtCode: event.target.value })}
        >
          <option value="">请选择区县</option>
          {districts.map(item => (
            <option key={item.region_code} value={item.region_code}>{item.name}</option>
          ))}
        </select>
      </div>
      <div className="form-hint">{selectedSummary || '请选择国家、省、市、区县后再继续。'}</div>
      {error && <div className="form-error">{error}</div>}
    </div>
  );
}
