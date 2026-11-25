"use client";

import React, { useState, useEffect } from "react";
import { SparklesIcon, CheckCircleIcon, BookmarkIcon, UserIcon } from "./Icons";

interface BookmarkletModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function BookmarkletModal({ isOpen, onClose }: BookmarkletModalProps) {
  const [childName, setChildName] = useState("김위례");
  const [birthDate, setBirthDate] = useState("2020-05-15");
  const [gender, setGender] = useState("F");
  const [parentName, setParentName] = useState("김보호");
  const [phoneNumber, setPhoneNumber] = useState("010-1234-5678");
  const [bookmarkletUrl, setBookmarkletUrl] = useState("");

  // Load from localStorage if present
  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("wirye_kids_profile");
      if (saved) {
        try {
          const data = JSON.parse(saved);
          if (data.childName) setChildName(data.childName);
          if (data.birthDate) setBirthDate(data.birthDate);
          if (data.gender) setGender(data.gender);
          if (data.parentName) setParentName(data.parentName);
          if (data.phoneNumber) setPhoneNumber(data.phoneNumber);
        } catch (e) {}
      }
    }
  }, []);

  // Update Bookmarklet JS Code
  useEffect(() => {
    const cleanBirth = birthDate.replace(/[-.]/g, "");
    const cleanPhone = phoneNumber.replace(/[-.]/g, "").trim();
    let p1 = "010", p2 = "", p3 = "";
    if (cleanPhone.length === 11) {
      p1 = cleanPhone.slice(0, 3);
      p2 = cleanPhone.slice(3, 7);
      p3 = cleanPhone.slice(7);
    } else if (cleanPhone.length === 10) {
      p1 = cleanPhone.slice(0, 3);
      p2 = cleanPhone.slice(3, 6);
      p3 = cleanPhone.slice(6);
    }

    const js = `javascript:(function(){
      var childName = ${JSON.stringify(childName)};
      var parentName = ${JSON.stringify(parentName)};
      var birthFull = ${JSON.stringify(birthDate)};
      var birthClean = ${JSON.stringify(cleanBirth)};
      var phoneFull = ${JSON.stringify(phoneNumber)};
      var p1 = ${JSON.stringify(p1)}, p2 = ${JSON.stringify(p2)}, p3 = ${JSON.stringify(p3)};
      var gender = ${JSON.stringify(gender)};
      var filledCount = 0;

      var nameSelectors = ["input[name*='name']","input[id*='name']","input[name*='applcnt']","input[name*='studnt']","input[name*='child']","input[name*='user_nm']"];
      document.querySelectorAll(nameSelectors.join(',')).forEach(function(el){
        if (el.type === 'text' || el.type === 'search') {
          var idOrName = (el.name + ' ' + el.id).toLowerCase();
          if (idOrName.indexOf('parent') !== -1 || idOrName.indexOf('prnt') !== -1) {
            el.value = parentName;
          } else {
            el.value = childName;
          }
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          filledCount++;
        }
      });

      var birthSelectors = ["input[name*='birth']","input[id*='birth']","input[name*='brthdy']"];
      document.querySelectorAll(birthSelectors.join(',')).forEach(function(el){
        el.value = (el.maxLength === 8) ? birthClean : birthFull;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        filledCount++;
      });

      var phoneSelectors = ["input[name*='tel']","input[name*='phone']","input[name*='mbtlnum']","input[name*='hp']"];
      var phoneInputs = Array.from(document.querySelectorAll(phoneSelectors.join(','))).filter(function(el){
        return el.type === 'text' || el.type === 'tel' || el.type === 'number';
      });

      if (phoneInputs.length >= 3) {
        phoneInputs[0].value = p1;
        phoneInputs[1].value = p2;
        phoneInputs[2].value = p3;
        phoneInputs.forEach(function(el){
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
        });
        filledCount += 3;
      } else if (phoneInputs.length === 1) {
        phoneInputs[0].value = phoneFull;
        phoneInputs[0].dispatchEvent(new Event('input', { bubbles: true }));
        phoneInputs[0].dispatchEvent(new Event('change', { bubbles: true }));
        filledCount++;
      }

      var checkboxes = document.querySelectorAll("input[type='checkbox']");
      checkboxes.forEach(function(chk){
        var parentTxt = (chk.parentElement ? chk.parentElement.innerText : '').toLowerCase();
        var chkId = (chk.id + ' ' + chk.name).toLowerCase();
        if (parentTxt.indexOf('동의') !== -1 || chkId.indexOf('agree') !== -1 || chkId.indexOf('chk') !== -1) {
          chk.checked = true;
          chk.dispatchEvent(new Event('change', { bubbles: true }));
          filledCount++;
        }
      });

      var genderRadios = document.querySelectorAll("input[type='radio'][value*='" + gender + "'], input[type='radio'][id*='" + (gender === 'M' ? 'male' : 'female') + "']");
      genderRadios.forEach(function(r){
        r.checked = true;
        r.dispatchEvent(new Event('change', { bubbles: true }));
      });

      var toast = document.createElement('div');
      toast.innerHTML = '⚡ <b>[위례키즈 부스터]</b> 자녀 정보(' + childName + ') 자동완성 및 약관동의 완료!';
      toast.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#059669;color:#fff;padding:14px 24px;border-radius:12px;font-size:15px;font-weight:bold;z-index:999999;box-shadow:0 10px 25px rgba(0,0,0,0.3);';
      document.body.appendChild(toast);
      setTimeout(function(){ toast.remove(); }, 3500);
    })();`.replace(/\n\s*/g, " ");

    setBookmarkletUrl(js);

    if (typeof window !== "undefined") {
      localStorage.setItem("wirye_kids_profile", JSON.stringify({
        childName, birthDate, gender, parentName, phoneNumber
      }));
    }
  }, [childName, birthDate, gender, parentName, phoneNumber]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white text-gray-900 rounded-3xl max-w-xl w-full p-6 sm:p-8 shadow-2xl border border-gray-100 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between pb-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-100 text-amber-600 flex items-center justify-center">
              <SparklesIcon className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight">위례키즈 예약 부스터 설정</h2>
              <p className="text-xs text-gray-500">도서관 신청 폼 원클릭 자동완성 북마클릿</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-gray-100 hover:bg-gray-200 text-gray-500 flex items-center justify-center transition"
          >
            ✕
          </button>
        </div>

        {/* Profile Inputs */}
        <div className="mt-6 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">자녀 이름</label>
              <input
                type="text"
                value={childName}
                onChange={(e) => setChildName(e.target.value)}
                placeholder="예: 홍길동"
                className="w-full px-3.5 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 bg-gray-50 focus:bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">자녀 생년월일</label>
              <input
                type="text"
                value={birthDate}
                onChange={(e) => setBirthDate(e.target.value)}
                placeholder="YYYY-MM-DD (예: 2020-05-15)"
                className="w-full px-3.5 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 bg-gray-50 focus:bg-white"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">자녀 성별</label>
              <select
                value={gender}
                onChange={(e) => setGender(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 bg-gray-50 focus:bg-white"
              >
                <option value="F">여아 (F)</option>
                <option value="M">남아 (M)</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">보호자 성명</label>
              <input
                type="text"
                value={parentName}
                onChange={(e) => setParentName(e.target.value)}
                placeholder="보호자 이름"
                className="w-full px-3.5 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 bg-gray-50 focus:bg-white"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1">보호자 연락처</label>
              <input
                type="text"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="010-XXXX-XXXX"
                className="w-full px-3.5 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 bg-gray-50 focus:bg-white"
              />
            </div>
          </div>
        </div>

        {/* Draggable Bookmarklet Button */}
        <div className="mt-6 p-5 rounded-2xl bg-amber-50/70 border-2 border-dashed border-amber-300 text-center">
          <p className="text-xs font-bold text-amber-900 mb-2">
            👇 아래 버튼을 마우스로 잡아서 **브라우저 북마크(즐겨찾기)바**로 드래그하세요!
          </p>
          <div className="inline-block my-2">
            <a
              href={bookmarkletUrl}
              onClick={(e) => {
                e.preventDefault();
                alert("이 버튼을 마우스로 끌어서(드래그) 웹브라우저 상단의 북마크바(즐겨찾기)에 놓아주세요!");
              }}
              draggable
              className="inline-flex items-center gap-2 px-6 py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-orange-500 text-white font-extrabold text-base shadow-lg shadow-orange-500/25 cursor-grab active:cursor-grabbing hover:scale-105 transition"
            >
              <BookmarkIcon className="w-5 h-5" />
              ⚡ [위례키즈 부스터: {childName}]
            </a>
          </div>
          <p className="text-[11px] text-gray-500 mt-1">
            * 사파리, 크롬, 엣지, 웨일 등 모든 브라우저의 북마크바에 등록 가능합니다.
          </p>
        </div>

        {/* Usage Step Guide */}
        <div className="mt-6 space-y-2.5 bg-gray-50 p-4 rounded-2xl">
          <h4 className="text-xs font-bold text-gray-800 uppercase tracking-wider">🎯 실제 예약 당일 사용 순서</h4>
          <ol className="text-xs text-gray-600 space-y-1.5 list-decimal list-inside">
            <li>위례키즈 웹앱에서 원하는 강좌의 <span className="font-semibold text-blue-600">[원클릭 신청하기]</span>를 누릅니다.</li>
            <li>도서관 신청 페이지(송파, 하남, 성남 배움숲)가 열리면 북마크바의 <span className="font-semibold text-amber-700">[위례키즈 부스터]</span>를 클릭합니다.</li>
            <li>0.1초 만에 <span className="text-emerald-700 font-semibold">자녀 이름, 생년월일, 연락처 입력 및 필수 약관 동의</span>가 자동 체크됩니다.</li>
            <li>마지막으로 [확인 / 접수신청] 버튼만 누르면 초고속 접수 완료!</li>
          </ol>
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl bg-gray-900 hover:bg-black text-white text-sm font-semibold transition"
          >
            설정 완료
          </button>
        </div>
      </div>
    </div>
  );
}
