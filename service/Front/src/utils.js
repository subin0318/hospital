export const extractRegion = (address = '') => {
  const match = address.match(/([가-힣]+(?:시|군|구))/);
  return match ? match[1] : '';
};

export const formatUpdateStatus = (hvidate) => {
  if (!hvidate) return '실시간 정보 미연동';
  if (hvidate.length >= 12) {
    const yyyy = hvidate.substring(0, 4);
    const mm = hvidate.substring(4, 6);
    const dd = hvidate.substring(6, 8);
    const hh = hvidate.substring(8, 10);
    const min = hvidate.substring(10, 12);
    return `${yyyy}-${mm}-${dd} ${hh}:${min}`;
  }
  return hvidate;
};
