package com.everydayadvertise.tv.ui.onboarding

import android.content.Context
import android.content.DialogInterface
import android.graphics.Color
import android.graphics.drawable.ColorDrawable
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import androidx.fragment.app.DialogFragment
import com.everydayadvertise.tv.R
import com.everydayadvertise.tv.api.PairCodeHolder

class OnboardingFragment : DialogFragment() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setStyle(STYLE_NORMAL, R.style.OnboardingDialogTheme)
        isCancelable = false
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? = inflater.inflate(R.layout.fragment_onboarding, container, false)

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        val continueButton = view.findViewById<Button>(R.id.onboardingContinueButton)
        continueButton.setOnClickListener { dismissAllowingStateLoss() }
        continueButton.requestFocus()
    }

    override fun onStart() {
        super.onStart()
        dialog?.window?.setLayout(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.MATCH_PARENT
        )
        dialog?.window?.setBackgroundDrawable(ColorDrawable(Color.TRANSPARENT))
    }

    override fun onDismiss(dialog: DialogInterface) {
        persistOnboardingComplete()
        super.onDismiss(dialog)
    }

    private fun persistOnboardingComplete() {
        val ctx = context ?: return
        ctx.getSharedPreferences(PairCodeHolder.PREFS_NAME, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_ONBOARDING_COMPLETE, true)
            .apply()
    }

    companion object {
        const val TAG = "OnboardingFragment"
        const val KEY_ONBOARDING_COMPLETE = "has_completed_onboarding"

        fun newInstance() = OnboardingFragment()
    }
}
